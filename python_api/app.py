"""Authenticated Classio Python inference boundary for the Expo client.

Run with PYTHONPATH=streamlit and an explicitly approved affinity run id. The
existing Streamlit algorithms remain the implementation of the model.
"""

from __future__ import annotations

import os
from typing import Annotated, Literal

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from helpers.recommendation_models import _fit_linear_model, _score_linear_model
from helpers.resource_affinity_runtime import load_resource_affinity_index, resource_affinity_score
from helpers.student_recommendation_ml import _base_student_weights, summarize_student_recommendation_samples
from helpers.program_resource_context import build_program_topic_generation_context, get_program_topic_recommendation_profile


app = FastAPI(title="Classio Python Models", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CLASSIO_EXPO_ORIGINS", "https://classio.expo.app").split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
RESOURCE_TABLE = {"plan": "lesson_plans", "worksheet": "worksheets", "exam": "quick_exams", "video": "videos"}


class AffinityRequest(BaseModel):
    kind: Literal["plan", "worksheet", "exam", "video"]
    resource_id: int = Field(gt=0)
    context: dict[str, str] = Field(default_factory=dict)


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


def _settings() -> tuple[str, str]:
    base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_PUBLISHABLE_KEY", "")
    if not base or not key:
        raise HTTPException(503, "Supabase authentication is not configured")
    return base, key


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/v1/models/resource-affinity")
def affinity_model(_actor: Annotated[tuple[str, str], Depends(actor_token)]) -> dict:
    if not os.getenv("CLASSIO_RESOURCE_AFFINITY_RUN_ID"):
        raise HTTPException(503, "An approved affinity run must be pinned")
    index = load_resource_affinity_index()
    if not index.get("available"):
        raise HTTPException(503, f"Affinity model unavailable: {index.get('reason')}")
    return {"run_id": index["run_id"], "winner": index["winner"], "model_family": index["model_family"], "feature_schema_version": index["representation_manifest"].get("feature_schema_version")}


@app.post("/v1/resource-affinity/score")
async def affinity_score(request: AffinityRequest, actor: Annotated[tuple[str, str], Depends(actor_token)]) -> dict:
    if not os.getenv("CLASSIO_RESOURCE_AFFINITY_RUN_ID"):
        raise HTTPException(503, "An approved affinity run must be pinned")
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
