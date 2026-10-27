"""Authenticated Classio Python inference boundary for the Expo client.

Run with PYTHONPATH=streamlit and an explicitly approved affinity run id. The
existing Streamlit algorithms remain the implementation of the model.
"""

from __future__ import annotations

import os
import asyncio
import hashlib
import json
import re
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from helpers.recommendation_models import _fit_linear_model, _score_linear_model
from helpers.resource_affinity_bundle import BUCKET as RUNTIME_BUCKET, MANIFEST_NAME as RUNTIME_MANIFEST, REQUIRED_FILES as RUNTIME_REQUIRED_FILES
from helpers.resource_affinity_runtime import RUNS_ROOT, load_resource_affinity_index, resource_affinity_score
from helpers.student_recommendation_ml import _base_student_weights, summarize_student_recommendation_samples
from helpers.program_resource_context import build_program_topic_generation_context, get_program_topic_recommendation_profile


app = FastAPI(title="Classio Python Models", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CLASSIO_EXPO_ORIGINS", "https://classio.expo.app,https://app.masterclassio.com").split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
RESOURCE_TABLE = {"plan": "lesson_plans", "worksheet": "worksheets", "exam": "quick_exams", "video": "videos"}
AFFINITY_EXPERIMENT_ID = "resource_affinity_unsupervised_discovery"
_bundle_lock = asyncio.Lock()
_ready_run_id = ""
_ready_model_name = ""


class AffinityRequest(BaseModel):
    kind: Literal["plan", "worksheet", "exam", "video"]
    resource_id: int = Field(gt=0)
    context: dict[str, str] = Field(default_factory=dict)


class AffinityBatchRequest(BaseModel):
    candidates: list[AffinityRequest] = Field(min_length=1, max_length=100)


class TrainingSample(BaseModel):
    features: dict[str, float]
    target: float = Field(ge=0, le=1)
    label: int = Field(default=0, ge=0, le=1)
    timestamp: str = ""
    kind: str = ""
    source: str = ""


class StudentScoreRequest(BaseModel):
    samples: list[TrainingSample] = Field(max_length=400)
    diagnostic_samples: list[TrainingSample] = Field(default_factory=list, max_length=400)
    candidates: list[dict[str, float]] = Field(min_length=1, max_length=100)


class AdminResetRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=100)
    scope: Literal["student", "teacher", "full"]
    archive_shared_resources: bool = True
    remove_relationships: bool = True
    notes: str = Field(default="", max_length=1000)
    confirm: bool = False
    confirmation_phrase: str = ""


def _settings() -> tuple[str, str]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    if not base or not key:
        raise HTTPException(503, "Supabase authentication is not configured")
    return base, key


async def _approved_affinity_run(client: httpx.AsyncClient, base: str, key: str, run_id: str) -> dict:
    response = await client.get(
        f"{base}/rest/v1/ml_experiment_runs",
        params={"select": "run_id,experiment_id,run_status,integrity_status,operational_use,is_current_validated_run,human_review_recommended_model_name", "run_id": f"eq.{run_id}", "limit": "1"},
        headers={"apikey": key, "Authorization": f"Bearer {key}"},
    )
    if response.status_code != 200:
        raise HTTPException(503, "Approved model registry is unavailable")
    rows = response.json()
    row = rows[0] if rows else {}
    if (
        row.get("experiment_id") != AFFINITY_EXPERIMENT_ID
        or row.get("operational_use") != "PRODUCTION_RUNTIME"
        or row.get("is_current_validated_run") is not True
        or row.get("run_status") not in {"VALIDATED_EXPLORATORY_RUN", "VALIDATED_NO_ROBUST_WINNER"}
        or not str(row.get("integrity_status") or "").startswith("PASSED")
        or not row.get("human_review_recommended_model_name")
    ):
        raise HTTPException(503, "The selected affinity run is not approved for runtime")
    return row


async def _ensure_affinity_bundle() -> dict:
    """Load only the active reviewed run from private storage, then verify bytes."""
    global _ready_run_id, _ready_model_name
    run_id = os.getenv("CLASSIO_RESOURCE_AFFINITY_RUN_ID", "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,80}", run_id):
        raise HTTPException(503, "An approved affinity run must be pinned")
    base, _ = _settings()
    secret = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or ""
    if not secret:
        raise HTTPException(503, "Private model storage is not configured")
    async with _bundle_lock:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                approved = await _approved_affinity_run(client, base, secret, run_id)
                if _ready_run_id == run_id and _ready_model_name == approved["human_review_recommended_model_name"]:
                    return approved
                prefix = f"{base}/storage/v1/object/authenticated/{RUNTIME_BUCKET}/resource_affinity/{run_id}/"
                headers = {"apikey": secret, "Authorization": f"Bearer {secret}"}
                response = await client.get(prefix + RUNTIME_MANIFEST, headers=headers)
                if response.status_code != 200:
                    raise HTTPException(503, "Approved runtime bundle has not been published")
                manifest = response.json()
                files = manifest.get("files") or {}
                if (
                    manifest.get("schema_version") != 1
                    or manifest.get("run_id") != run_id
                    or manifest.get("model_name") != approved["human_review_recommended_model_name"]
                    or not isinstance(files, dict)
                    or not set(RUNTIME_REQUIRED_FILES).issubset(files)
                    or len(files) > 12
                ):
                    raise HTTPException(503, "Approved runtime bundle manifest is invalid")
                run_dir = RUNS_ROOT / run_id
                run_dir.mkdir(parents=True, exist_ok=True)
                for name, metadata in files.items():
                    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", name) or name.startswith(".") or not isinstance(metadata, dict):
                        raise HTTPException(503, "Approved runtime bundle contains an invalid file")
                    expected = metadata.get("sha256")
                    size = metadata.get("size")
                    if not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected) or not isinstance(size, int) or size < 1 or size > 10_000_000:
                        raise HTTPException(503, "Approved runtime bundle contains invalid metadata")
                    target = run_dir / name
                    if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == expected:
                        continue
                    file_response = await client.get(prefix + name, headers=headers)
                    if file_response.status_code != 200 or len(file_response.content) != size or hashlib.sha256(file_response.content).hexdigest() != expected:
                        raise HTTPException(503, "Approved runtime bundle failed integrity verification")
                    temporary = run_dir / f".{name}.part"
                    temporary.write_bytes(file_response.content)
                    temporary.replace(target)
                (run_dir / RUNTIME_MANIFEST).write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
                load_resource_affinity_index.cache_clear()
                index = load_resource_affinity_index()
                if not index.get("available") or index.get("run_id") != run_id or index.get("winner") != approved["human_review_recommended_model_name"]:
                    raise HTTPException(503, "Approved runtime representation cannot be loaded")
                _ready_run_id = run_id
                _ready_model_name = approved["human_review_recommended_model_name"]
                return approved
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Approved model storage is unavailable") from exc


async def actor_token(authorization: Annotated[str | None, Header()] = None) -> tuple[str, str]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Classio sign-in is required")
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(401, "Classio sign-in is required")
    base, key = _settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{base}/auth/v1/user", headers={"apikey": key, "Authorization": f"Bearer {token}"})
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Classio authentication is unavailable") from exc
    if response.status_code != 200:
        raise HTTPException(401, "Classio session has expired")
    actor = str(response.json().get("id") or "")
    if not actor:
        raise HTTPException(401, "Classio session has expired")
    return actor, token


async def admin_actor(actor: Annotated[tuple[str, str], Depends(actor_token)]) -> str:
    user_id, _ = actor
    base, _ = _settings()
    secret = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY") or ""
    if not secret:
        raise HTTPException(503, "Private admin data access is not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{base}/rest/v1/profiles",
                params={"select": "role", "user_id": f"eq.{user_id}", "limit": "1"},
                headers={"apikey": secret, "Authorization": f"Bearer {secret}"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Admin access could not be verified") from exc
    if response.status_code != 200:
        raise HTTPException(503, "Admin access could not be verified")
    rows = response.json()
    if not rows or rows[0].get("role") != "admin":
        raise HTTPException(403, "Admin access is required")
    os.environ["SUPABASE_KEY"] = secret
    return user_id


@app.post("/v1/admin/account-reset/preview")
async def admin_account_reset_preview(request: AdminResetRequest, _admin: Annotated[str, Depends(admin_actor)]) -> dict:
    from core.database import get_sb
    from services.account_reset_service import build_user_reset_preview

    target = await run_in_threadpool(lambda: get_sb().table("profiles").select("user_id").eq("user_id", request.user_id).limit(1).execute())
    if not getattr(target, "data", None):
        raise HTTPException(404, "Account not found")

    return await run_in_threadpool(
        build_user_reset_preview,
        request.user_id,
        request.scope,
        archive_shared_resources=request.archive_shared_resources,
        remove_relationships=request.remove_relationships,
    )


@app.post("/v1/admin/account-reset/execute")
async def admin_account_reset_execute(request: AdminResetRequest, admin_id: Annotated[str, Depends(admin_actor)]) -> dict:
    expected = f"RESTART {request.scope.upper()}"
    if not request.confirm or request.confirmation_phrase.strip().upper() != expected:
        raise HTTPException(400, "Account reset confirmation is incomplete")
    if request.user_id == admin_id:
        raise HTTPException(400, "An admin cannot reset their own account")
    from core.database import get_sb
    from services.account_reset_service import execute_user_reset

    def perform() -> dict:
        target = get_sb().table("profiles").select("user_id").eq("user_id", request.user_id).limit(1).execute()
        if not getattr(target, "data", None):
            raise HTTPException(404, "Account not found")
        ok, message, counters = execute_user_reset(
            request.user_id,
            request.scope,
            notes=request.notes,
            archive_shared_resources=request.archive_shared_resources,
            remove_relationships=request.remove_relationships,
        )
        if not ok:
            raise HTTPException(500, f"Account reset failed: {message}")
        try:
            audit = get_sb().table("admin_overrides").insert({
                "user_id": request.user_id,
                "override_type": "restart_account",
                "reason": f"{request.scope}: {request.notes or 'Account reset'}",
                "created_by": admin_id,
            }).execute()
            audited = bool(getattr(audit, "data", None))
        except Exception:
            audited = False
        return {"ok": True, "audited": audited, "counters": counters}

    return await run_in_threadpool(perform)


@app.get("/v1/admin/intelligence")
async def admin_intelligence(_admin: Annotated[str, Depends(admin_actor)], language: Literal["en", "es", "tr"] = "en") -> dict:
    """Reuse the exact Streamlit EIC business rules for the Expo admin view."""
    from services import eic_service
    from services.eic_report_service import list_available_eic_reports

    def load() -> dict:
        summary = eic_service.get_intelligence_business_summary()
        validated = eic_service.list_validated_experiment_summaries(limit=10)
        latest = summary.get("latest_validated_run") or {}
        run_id = str(latest.get("run_id") or "")
        reports = list_available_eic_reports(run_id, set(), language=language) if run_id else []
        return {
            "summary": summary,
            "portfolio": eic_service.get_intelligence_component_portfolio(),
            "validated_runs": validated,
            "telemetry": eic_service.get_business_telemetry_health(),
            "decisions": eic_service.get_prioritized_intelligence_decisions(),
            "trend": eic_service.get_evidence_trend(),
            "business_detail": eic_service.get_experiment_business_detail(run_id) if run_id else {},
            "academic_evidence": eic_service.get_academic_evidence_summary(run_id) if run_id else {},
            "reports": [{key: row.get(key) for key in ("report_type", "title", "description", "status", "download_ready", "modified_at")} for row in reports],
        }

    return await run_in_threadpool(load)


@app.get("/v1/admin/intelligence/reports/{report_type}")
async def admin_intelligence_report(
    report_type: str,
    _actor: Annotated[str, Depends(admin_actor)],
    language: Literal["en", "es", "tr"] = "en",
) -> FileResponse:
    if report_type != "experiment_docx":
        raise HTTPException(404, "Report unavailable")
    from pathlib import Path
    from services import eic_service
    from services.eic_report_service import list_available_eic_reports

    def ready_report() -> Path:
        latest = (eic_service.get_intelligence_business_summary().get("latest_validated_run") or {})
        run_id = str(latest.get("run_id") or "")
        if not run_id:
            raise HTTPException(404, "No validated report is available")
        report = next((row for row in list_available_eic_reports(run_id, set(), language=language) if row.get("report_type") == report_type), None)
        if not report or not report.get("download_ready"):
            raise HTTPException(404, "The validated report has not been prepared")
        path = Path(str(report.get("path") or ""))
        if not path.is_file():
            raise HTTPException(404, "The validated report is unavailable")
        return path

    path = await run_in_threadpool(ready_report)
    return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=path.name)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/auth/check")
def auth_check(_actor: Annotated[tuple[str, str], Depends(actor_token)]) -> dict[str, bool]:
    """Verify Expo's Supabase bearer token without disclosing model state."""
    return {"authenticated": True}


@app.get("/v1/models/resource-affinity")
async def affinity_model(_actor: Annotated[tuple[str, str], Depends(actor_token)]) -> dict:
    await _ensure_affinity_bundle()
    index = load_resource_affinity_index()
    if not index.get("available"):
        raise HTTPException(503, f"Affinity model unavailable: {index.get('reason')}")
    return {"run_id": index["run_id"], "winner": index["winner"], "model_family": index["model_family"], "feature_schema_version": index["representation_manifest"].get("feature_schema_version")}


@app.post("/v1/resource-affinity/score")
async def affinity_score(request: AffinityRequest, actor: Annotated[tuple[str, str], Depends(actor_token)]) -> dict:
    await _ensure_affinity_bundle()
    base, key = _settings()
    owner_id, token = actor
    table = RESOURCE_TABLE[request.kind]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{base}/rest/v1/{table}",
                params={"select": "*", "id": f"eq.{request.resource_id}", "limit": "1"},
                headers={"apikey": key, "Authorization": f"Bearer {token}"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Resource lookup is unavailable") from exc
    if response.status_code != 200:
        raise HTTPException(503, "Resource lookup failed")
    rows = response.json()
    if not rows:
        raise HTTPException(404, "Resource unavailable")
    row = rows[0]
    if row.get("user_id") != owner_id and row.get("is_public") is not True:
        raise HTTPException(404, "Resource unavailable")
    if str(row.get("status") or "").lower() == "archived":
        raise HTTPException(404, "Resource unavailable")
    context = {key: value[:500] for key, value in request.context.items() if key in {"topic", "objective", "lesson_purpose", "worksheet_type", "focus_kind", "subject", "learner_stage", "level_or_band"}}
    score, diagnostics = resource_affinity_score(row, request.kind, context)
    if not diagnostics.get("available"):
        raise HTTPException(503, f"Affinity model unavailable: {diagnostics.get('reason')}")
    return {"score": round(float(score), 6), "run_id": diagnostics.get("run_id"), "matched": bool(diagnostics.get("matched")), "model_family": diagnostics.get("model_family")}


@app.post("/v1/resource-affinity/score-batch")
async def affinity_score_batch(request: AffinityBatchRequest, actor: Annotated[tuple[str, str], Depends(actor_token)]) -> dict:
    await _ensure_affinity_bundle()
    base, key = _settings()
    owner_id, token = actor
    headers = {"apikey": key, "Authorization": f"Bearer {token}"}
    rows_by_kind: dict[str, dict[int, dict]] = {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for kind in {candidate.kind for candidate in request.candidates}:
                ids = sorted({candidate.resource_id for candidate in request.candidates if candidate.kind == kind})
                response = await client.get(
                    f"{base}/rest/v1/{RESOURCE_TABLE[kind]}",
                    params={"select": "*", "id": f"in.({','.join(str(value) for value in ids)})", "limit": str(len(ids))},
                    headers=headers,
                )
                if response.status_code != 200:
                    raise HTTPException(503, "Resource lookup failed")
                rows_by_kind[kind] = {int(row["id"]): row for row in response.json() if row.get("id") is not None}
    except httpx.HTTPError as exc:
        raise HTTPException(503, "Resource lookup is unavailable") from exc
    results = []
    for candidate in request.candidates:
        row = rows_by_kind.get(candidate.kind, {}).get(candidate.resource_id)
        if not row or (row.get("user_id") != owner_id and row.get("is_public") is not True) or str(row.get("status") or "").lower() == "archived":
            results.append(None)
            continue
        context = {field: value[:500] for field, value in candidate.context.items() if field in {"topic", "objective", "lesson_purpose", "worksheet_type", "focus_kind", "subject", "learner_stage", "level_or_band"}}
        score, diagnostics = resource_affinity_score(row, candidate.kind, context)
        results.append({"score": round(float(score), 6), "matched": bool(diagnostics.get("matched"))} if diagnostics.get("available") else None)
    return {"run_id": load_resource_affinity_index().get("run_id"), "scores": results}


@app.post("/v1/student-recommendations/score")
def student_scores(request: StudentScoreRequest, _actor: Annotated[tuple[str, str], Depends(actor_token)]) -> dict:
    """Score owner-scoped features supplied by Expo using the existing Python fit."""
    samples = [sample.model_dump() for sample in request.samples]
    diagnostic_samples = [sample.model_dump() for sample in request.diagnostic_samples]
    if any(len(sample["features"]) > 64 for sample in samples + diagnostic_samples) or any(len(candidate) > 64 for candidate in request.candidates):
        raise HTTPException(400, "Too many features")
    weights = _fit_linear_model([(sample["features"], sample["target"]) for sample in samples], base_weights=_base_student_weights())
    diagnostic = summarize_student_recommendation_samples(diagnostic_samples)
    return {"scores": [round(_score_linear_model(weights, features), 6) for features in request.candidates], "blend_weight": diagnostic["blend_weight"], "sample_count": len(samples), "model_version": "student_recommendation_python_v1"}


@app.get("/v1/program-topics/{program_id}/{topic_id}/recommendations")
async def program_topic_recommendations(program_id: int, topic_id: int, actor: Annotated[tuple[str, str], Depends(actor_token)]) -> dict:
    if program_id <= 0 or topic_id <= 0:
        raise HTTPException(400, "Choose a valid program topic")
    base, key = _settings()
    owner_id, token = actor
    headers = {"apikey": key, "Authorization": f"Bearer {token}"}

    async def first(table: str, select: str, filters: dict[str, str]) -> dict | None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{base}/rest/v1/{table}", params={"select": select, "limit": "1", **filters}, headers=headers)
        except httpx.HTTPError as exc:
            raise HTTPException(503, "Program topic lookup is unavailable") from exc
        if response.status_code != 200:
            raise HTTPException(503, "Program topic lookup failed")
        rows = response.json()
        return rows[0] if rows else None

    program = await first("learning_programs", "id,title,subject,custom_subject_name,learner_stage,level_or_band,program_overview,assessment_strategy,resource_strategy,status", {"id": f"eq.{program_id}", "user_id": f"eq.{owner_id}"})
    if not program or program.get("status") == "archived":
        raise HTTPException(404, "Program unavailable")
    topic = await first("learning_program_topics", "id,program_id,unit_number,topic_number,title,subtopic,lesson_focus,student_summary,learning_objectives,success_criteria,student_can_do,lesson_purpose,suggested_worksheet_types,suggested_exam_exercise_types", {"id": f"eq.{topic_id}", "program_id": f"eq.{program_id}"})
    if not topic:
        raise HTTPException(404, "Program topic unavailable")
    unit = await first("learning_program_units", "id,unit_number,title,overview", {"program_id": f"eq.{program_id}", "unit_number": f"eq.{topic.get('unit_number')}"})
    subject = str(program.get("subject") or "")
    context = build_program_topic_generation_context(program, unit or {}, topic, subject=subject, custom_subject_name=str(program.get("custom_subject_name") or ""), learner_stage=str(program.get("learner_stage") or ""), level_or_band=str(program.get("level_or_band") or ""))
    result = get_program_topic_recommendation_profile(context)
    return {"program_id": program_id, "topic_id": topic_id, "worksheet_ranked": result["worksheet_ranked"], "exam_ranked": result["exam_ranked"], "lesson_purpose_ranked": result["lesson_purpose_ranked"], "source": "python_program_topic_recommendation_v1"}
