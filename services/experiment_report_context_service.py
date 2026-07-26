from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

import streamlit as st

from core.database import get_sb, json_safe
from core.state import get_current_user_id


REPORT_CONTEXT_TABLE = "experiment_report_contexts"
REPORT_CONTEXT_ROOT = Path("reports") / "ml_architecture" / "eic_reports"
SUPPORTED_LANGUAGES = {"en", "es", "tr"}

PURPOSE_OPTIONS = (
    "infrastructure_validation",
    "engagement_prediction",
    "recommendation_optimization",
    "learning_outcome_prediction",
    "churn_or_disengagement_detection",
    "operational_efficiency",
    "other",
)

DECISION_OPTIONS = (
    "maintain_current_heuristic",
    "continue_collecting_data",
    "run_another_evaluation",
    "move_to_shadow_testing",
    "start_controlled_pilot",
    "reject_current_approach",
    "archive_experiment",
    "other",
)

AUDIENCE_OPTIONS = (
    "leadership_meeting",
    "product_review",
    "data_science_review",
    "technical_review",
    "school_administration",
    "mixed_audience",
)

LOCAL_ONLY_CONTEXT_FIELDS = (
    "main_limitation",
    "evidence_non_proof",
    "recommended_next_action",
)

REQUIRED_CONTEXT_FIELDS = (
    "purpose_key",
    "decision_under_consideration_key",
    "audience_key",
    "business_problem",
    "decision_supported",
    "expected_value",
    "product_impact",
    "success_definition",
    "minimum_evidence_required",
    "risks",
    "main_limitation",
    "evidence_non_proof",
    "recommended_next_action",
    "next_review_trigger",
    "next_review_date",
    "responsible_person_or_team",
    "meeting_notes",
)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _lang(language: str | None) -> str:
    safe = _clean_text(language).lower()
    return safe if safe in SUPPORTED_LANGUAGES else "en"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _supabase_storage_enabled() -> bool:
    return str(os.getenv("EXPERIMENT_REPORT_CONTEXT_STORAGE", "local") or "").strip().lower() == "supabase"


def _report_dir(run_id: str, language: str) -> Path:
    return REPORT_CONTEXT_ROOT / _clean_text(run_id) / _lang(language)


def _context_cache_path(run_id: str, language: str) -> Path:
    safe_run_id = _clean_text(run_id)
    safe_lang = _lang(language)
    return REPORT_CONTEXT_ROOT / safe_run_id / f"report_context_{safe_lang}.json"


def _write_local_context(payload: dict[str, Any]) -> None:
    cache_path = _context_cache_path(str(payload.get("run_id") or ""), str(payload.get("language") or "en"))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_local_context(run_id: str, language: str) -> dict[str, Any] | None:
    cache_path = _context_cache_path(run_id, language)
    if not cache_path.exists():
        return None
    try:
        return json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _load_any_language_context(run_id: str) -> dict[str, Any] | None:
    safe_run_id = _clean_text(run_id)
    if not safe_run_id:
        return None
    if _supabase_storage_enabled():
        try:
            response = (
                get_sb()
                .table(REPORT_CONTEXT_TABLE)
                .select("*")
                .eq("run_id", safe_run_id)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = getattr(response, "data", None) or []
            if rows:
                row = dict(rows[0])
                _write_local_context(row)
                return row
        except Exception:
            pass
    root = REPORT_CONTEXT_ROOT / safe_run_id
    if not root.exists():
        return None
    latest_path: Path | None = None
    latest_mtime = -1.0
    for path in root.glob("report_context_*.json"):
        try:
            mtime = path.stat().st_mtime
        except Exception:
            continue
        if mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = path
    if latest_path is None:
        return None
    try:
        return json.loads(latest_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _clear_cached_reports(run_id: str, language: str) -> None:
    report_dir = _report_dir(run_id, language)
    if not report_dir.exists():
        return
    for path in report_dir.glob("*.docx"):
        try:
            path.unlink()
        except Exception:
            pass


def _default_context(run_id: str, experiment_id: str, language: str) -> dict[str, Any]:
    safe_lang = _lang(language)
    localized = _localized_default_text(_clean_text(experiment_id), safe_lang)
    return {
        "run_id": _clean_text(run_id),
        "experiment_id": _clean_text(experiment_id),
        "language": safe_lang,
        "purpose_key": localized.get("purpose_key", ""),
        "decision_under_consideration_key": localized.get("decision_under_consideration_key", ""),
        "audience_key": localized.get("audience_key", ""),
        "business_problem": localized.get("business_problem", ""),
        "decision_supported": localized.get("decision_supported", ""),
        "expected_value": localized.get("expected_value", ""),
        "product_impact": localized.get("product_impact", ""),
        "success_definition": localized.get("success_definition", ""),
        "minimum_evidence_required": localized.get("minimum_evidence_required", ""),
        "risks": localized.get("risks", ""),
        "main_limitation": localized.get("main_limitation", ""),
        "evidence_non_proof": localized.get("evidence_non_proof", ""),
        "recommended_next_action": localized.get("recommended_next_action", ""),
        "next_review_trigger": localized.get("next_review_trigger", ""),
        "next_review_date": "",
        "responsible_person_or_team": localized.get("responsible_person_or_team", ""),
        "meeting_notes": localized.get("meeting_notes", ""),
        "created_by": "",
        "created_at": "",
        "updated_at": "",
    }


def _localized_default_text(experiment_id: str, language: str) -> dict[str, str]:
    safe_lang = _lang(language)
    safe_experiment = _clean_text(experiment_id)
    defaults: dict[str, dict[str, dict[str, str]]] = {
        "student_recommendation_open_within_7d": {
            "en": {
                "purpose_key": "engagement_prediction",
                "decision_under_consideration_key": "continue_collecting_data",
                "audience_key": "mixed_audience",
                "business_problem": "Can Classio predict whether a student will open an optional recommendation within seven days of seeing it?",
                "decision_supported": "Whether the student recommendation feed has enough first-party exposure evidence to compare learned ranking against the current heuristic.",
                "expected_value": "Improve optional practice follow-through without mixing subjects, teachers, or completed assignments.",
                "product_impact": "Student Home and Smart Practice recommendation ordering.",
                "success_definition": "A supervised model beats the dummy baseline on ROC-AUC and average precision with credible chronological validation.",
                "minimum_evidence_required": "Enough mature recommendation exposures with matched open events across the supported languages and relevant student scopes.",
                "risks": "Sparse exposure logging can make the model overfit to a small number of students, teachers, or subjects.",
                "main_limitation": "The label is a proxy for engagement, not direct learning gain.",
                "evidence_non_proof": "A higher open probability does not prove better learning outcomes.",
                "recommended_next_action": "Continue collecting exposure and open telemetry before any live deployment.",
                "next_review_trigger": "Re-run once recommendation exposure coverage grows materially or after two months of new data.",
                "responsible_person_or_team": "Classio product and data science team.",
            },
            "es": {
                "purpose_key": "engagement_prediction",
                "decision_under_consideration_key": "continue_collecting_data",
                "audience_key": "mixed_audience",
                "business_problem": "¿Puede Classio predecir si un estudiante abrirá una recomendación opcional dentro de siete días después de verla?",
                "decision_supported": "Si el feed de recomendaciones del estudiante tiene suficiente evidencia propia de exposiciones para comparar un ranking aprendido contra la heurística actual.",
                "expected_value": "Mejorar el seguimiento de práctica opcional sin mezclar materias, profesores ni tareas completadas.",
                "product_impact": "Orden de recomendaciones en Inicio del estudiante y Smart Practice.",
                "success_definition": "Un modelo supervisado supera al baseline dummy en ROC-AUC y average precision con una validación cronológica creíble.",
                "minimum_evidence_required": "Suficientes exposiciones maduras de recomendaciones con eventos de apertura vinculados en los idiomas soportados y scopes relevantes del estudiante.",
                "risks": "La telemetría escasa de exposiciones puede hacer que el modelo se sobreajuste a pocos estudiantes, profesores o materias.",
                "main_limitation": "La etiqueta es un proxy de engagement, no una ganancia directa de aprendizaje.",
                "evidence_non_proof": "Una mayor probabilidad de apertura no demuestra mejores resultados de aprendizaje.",
                "recommended_next_action": "Seguir recolectando telemetría de exposiciones y aperturas antes de cualquier despliegue en vivo.",
                "next_review_trigger": "Repetir cuando la cobertura de exposiciones crezca materialmente o después de dos meses de datos nuevos.",
                "responsible_person_or_team": "Equipo de producto y ciencia de datos de Classio.",
            },
            "tr": {
                "purpose_key": "engagement_prediction",
                "decision_under_consideration_key": "continue_collecting_data",
                "audience_key": "mixed_audience",
                "business_problem": "Classio, bir öğrencinin isteğe bağlı bir öneriyi gördükten sonraki yedi gün içinde açıp açmayacağını tahmin edebilir mi?",
                "decision_supported": "Öğrenci öneri akışında öğrenilmiş sıralamayı mevcut sezgisel yaklaşımla karşılaştırmaya yetecek birinci taraf gösterim kanıtı olup olmadığı.",
                "expected_value": "Dersleri, öğretmenleri veya tamamlanmış ödevleri karıştırmadan isteğe bağlı pratik katılımını artırmak.",
                "product_impact": "Öğrenci Ana Sayfası ve Smart Practice öneri sıralaması.",
                "success_definition": "Denetimli modelin kronolojik doğrulamada ROC-AUC ve average precision açısından dummy baseline'ı geçmesi.",
                "minimum_evidence_required": "Desteklenen dillerde ve ilgili öğrenci kapsamlarında açılma olaylarıyla eşleşmiş yeterli olgun öneri gösterimi.",
                "risks": "Seyrek gösterim telemetrisi modelin az sayıda öğrenci, öğretmen veya derse aşırı uyum sağlamasına yol açabilir.",
                "main_limitation": "Etiket doğrudan öğrenme kazanımı değil, etkileşim için bir proxy'dir.",
                "evidence_non_proof": "Daha yüksek açılma olasılığı daha iyi öğrenme sonucunu kanıtlamaz.",
                "recommended_next_action": "Canlı kullanımdan önce gösterim ve açılma telemetrisini toplamaya devam edin.",
                "next_review_trigger": "Öneri gösterim kapsamı belirgin şekilde büyüdüğünde veya iki aylık yeni veri sonrasında yeniden çalıştırın.",
                "responsible_person_or_team": "Classio ürün ve veri bilimi ekibi.",
            },
        },
        "resource_affinity_unsupervised_discovery": {
            "en": {
                "purpose_key": "recommendation_optimization",
                "decision_under_consideration_key": "move_to_shadow_testing",
                "audience_key": "mixed_audience",
                "business_problem": "Can Classio discover semantic relationships between educational resources without manual labels to improve recommendation candidates and similar-resource warnings?",
                "decision_supported": "Whether unsupervised resource-affinity discovery is credible enough to expand recommendation candidates and pre-generation warnings in shadow mode.",
                "expected_value": "Find related resources by meaning, not only by exact topic text or manual tags.",
                "product_impact": "Teacher recommendations and pre-generation similar-resource warnings.",
                "success_definition": "A clustering model wins on silhouette quality while producing semantically useful neighbor groups under human review.",
                "minimum_evidence_required": "A sufficiently broad resource inventory across Classio's supported languages and resource types.",
                "risks": "Cluster metrics are proxies; semantic quality still needs human review before production decisions.",
                "main_limitation": "Unsupervised cluster quality does not prove recommendation effectiveness.",
                "evidence_non_proof": "A good cluster does not prove the student or teacher will prefer the resource.",
                "recommended_next_action": "Use the winning model in Phase 2 shadow scoring and monitor recommendation quality before deployment.",
                "next_review_trigger": "Re-run after a larger resource inventory or after two months of production shadow telemetry.",
                "responsible_person_or_team": "Classio product and data science team.",
            },
            "es": {
                "purpose_key": "recommendation_optimization",
                "decision_under_consideration_key": "move_to_shadow_testing",
                "audience_key": "mixed_audience",
                "business_problem": "¿Puede Classio descubrir relaciones semánticas entre recursos educativos sin etiquetas manuales para mejorar candidatos de recomendación y avisos de recursos similares?",
                "decision_supported": "Si el descubrimiento no supervisado de afinidad entre recursos es suficientemente creíble para ampliar candidatos de recomendación y avisos previos a la generación en modo sombra.",
                "expected_value": "Encontrar recursos relacionados por significado, no solo por texto exacto del tema o etiquetas manuales.",
                "product_impact": "Recomendaciones docentes y avisos de recursos similares antes de generar materiales.",
                "success_definition": "Un modelo de clustering gana en calidad de silhouette y produce grupos de vecinos semánticamente útiles bajo revisión humana.",
                "minimum_evidence_required": "Un inventario de recursos suficientemente amplio en los idiomas y tipos de recurso soportados por Classio.",
                "risks": "Las métricas de clustering son proxies; la calidad semántica aún requiere revisión humana antes de decisiones productivas.",
                "main_limitation": "La calidad de clustering no supervisado no demuestra efectividad de recomendación.",
                "evidence_non_proof": "Un buen cluster no demuestra que el estudiante o profesor prefiera el recurso.",
                "recommended_next_action": "Usar el modelo ganador en el scoring sombra de Fase 2 y monitorear la calidad de recomendaciones antes del despliegue.",
                "next_review_trigger": "Repetir con un inventario mayor de recursos o después de dos meses de telemetría sombra en producción.",
                "responsible_person_or_team": "Equipo de producto y ciencia de datos de Classio.",
            },
            "tr": {
                "purpose_key": "recommendation_optimization",
                "decision_under_consideration_key": "move_to_shadow_testing",
                "audience_key": "mixed_audience",
                "business_problem": "Classio, manuel etiketler olmadan eğitim kaynakları arasındaki anlamsal ilişkileri keşfederek öneri adaylarını ve benzer kaynak uyarılarını iyileştirebilir mi?",
                "decision_supported": "Denetimsiz kaynak yakınlığı keşfinin öneri adaylarını ve üretim öncesi uyarıları gölge modda genişletmek için yeterince güvenilir olup olmadığı.",
                "expected_value": "Kaynakları yalnızca birebir konu metni veya manuel etiketlerle değil, anlamlarına göre ilişkilendirmek.",
                "product_impact": "Öğretmen önerileri ve üretim öncesi benzer kaynak uyarıları.",
                "success_definition": "Bir kümeleme modelinin silhouette kalitesinde öne çıkması ve insan incelemesinde anlamsal olarak yararlı komşu gruplar üretmesi.",
                "minimum_evidence_required": "Classio'nun desteklediği diller ve kaynak türleri genelinde yeterince geniş bir kaynak envanteri.",
                "risks": "Kümeleme metrikleri proxy'dir; üretim kararlarından önce anlamsal kalite hâlâ insan incelemesi gerektirir.",
                "main_limitation": "Denetimsiz küme kalitesi öneri etkinliğini kanıtlamaz.",
                "evidence_non_proof": "İyi bir küme öğrencinin veya öğretmenin kaynağı tercih edeceğini kanıtlamaz.",
                "recommended_next_action": "Kazanan modeli Faz 2 gölge skorlamasında kullanın ve dağıtımdan önce öneri kalitesini izleyin.",
                "next_review_trigger": "Daha büyük kaynak envanteriyle veya iki aylık üretim gölge telemetrisi sonrasında yeniden çalıştırın.",
                "responsible_person_or_team": "Classio ürün ve veri bilimi ekibi.",
            },
        },
    }
    return dict((defaults.get(safe_experiment) or {}).get(safe_lang) or {})


def get_report_context(run_id: str, experiment_id: str, language: str) -> dict[str, Any]:
    safe_run_id = _clean_text(run_id)
    safe_experiment_id = _clean_text(experiment_id)
    safe_lang = _lang(language)
    if not safe_run_id:
        return _default_context(safe_run_id, safe_experiment_id, safe_lang)
    if _supabase_storage_enabled():
        try:
            response = (
                get_sb()
                .table(REPORT_CONTEXT_TABLE)
                .select("*")
                .eq("run_id", safe_run_id)
                .eq("language", safe_lang)
                .limit(1)
                .execute()
            )
            rows = getattr(response, "data", None) or []
            if rows:
                row = dict(rows[0])
                row.setdefault("experiment_id", safe_experiment_id)
                row.setdefault("language", safe_lang)
                local_row = _read_local_context(safe_run_id, safe_lang) or {}
                merged = {**_default_context(safe_run_id, safe_experiment_id, safe_lang), **row, **dict(local_row)}
                _write_local_context(merged)
                return merged
        except Exception:
            pass
    local_row = _read_local_context(safe_run_id, safe_lang)
    if local_row:
        local_row = dict(local_row)
        local_row["language"] = safe_lang
        local_row.setdefault("experiment_id", safe_experiment_id)
        return {**_default_context(safe_run_id, safe_experiment_id, safe_lang), **local_row}
    cross_language = _load_any_language_context(safe_run_id)
    if cross_language:
        fallback_row = dict(cross_language)
        fallback_row["language"] = safe_lang
        fallback_row.setdefault("experiment_id", safe_experiment_id)
        localized_default = _default_context(safe_run_id, safe_experiment_id, safe_lang)
        for field in REQUIRED_CONTEXT_FIELDS:
            if field not in {"purpose_key", "decision_under_consideration_key", "audience_key", "next_review_date"}:
                fallback_row.pop(field, None)
        return {**localized_default, **fallback_row}
    return _default_context(safe_run_id, safe_experiment_id, safe_lang)


def save_report_context(payload: dict[str, Any]) -> dict[str, Any]:
    safe_run_id = _clean_text(payload.get("run_id"))
    safe_experiment_id = _clean_text(payload.get("experiment_id"))
    safe_lang = _lang(payload.get("language"))
    now_text = _now_iso()
    current_user_id = _clean_text(get_current_user_id())
    base = {
        "run_id": safe_run_id,
        "experiment_id": safe_experiment_id,
        "language": safe_lang,
        "purpose_key": _clean_text(payload.get("purpose_key")),
        "decision_under_consideration_key": _clean_text(payload.get("decision_under_consideration_key")),
        "audience_key": _clean_text(payload.get("audience_key")),
        "business_problem": _clean_text(payload.get("business_problem")),
        "decision_supported": _clean_text(payload.get("decision_supported")),
        "expected_value": _clean_text(payload.get("expected_value")),
        "product_impact": _clean_text(payload.get("product_impact")),
        "success_definition": _clean_text(payload.get("success_definition")),
        "minimum_evidence_required": _clean_text(payload.get("minimum_evidence_required")),
        "risks": _clean_text(payload.get("risks")),
        "next_review_trigger": _clean_text(payload.get("next_review_trigger")),
        "next_review_date": _clean_text(payload.get("next_review_date")),
        "responsible_person_or_team": _clean_text(payload.get("responsible_person_or_team")),
        "meeting_notes": _clean_text(payload.get("meeting_notes")),
        "updated_at": now_text,
    }
    local_only = {field: _clean_text(payload.get(field)) for field in LOCAL_ONLY_CONTEXT_FIELDS}
    if not _supabase_storage_enabled():
        fallback = {
            **_default_context(safe_run_id, safe_experiment_id, safe_lang),
            **base,
            "created_by": current_user_id,
            "created_at": now_text,
            "updated_at": now_text,
            **local_only,
            "_storage_status": "local_cache",
        }
        _write_local_context(fallback)
        _clear_cached_reports(safe_run_id, safe_lang)
        return fallback
    try:
        response = (
            get_sb()
            .table(REPORT_CONTEXT_TABLE)
            .select("*")
            .eq("run_id", safe_run_id)
            .eq("language", safe_lang)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        if rows:
            record_id = rows[0].get("id")
            result = (
                get_sb()
                .table(REPORT_CONTEXT_TABLE)
                .update(json_safe(base))
                .eq("id", record_id)
                .execute()
            )
            saved = (getattr(result, "data", None) or [base])[0]
        else:
            create_payload = {
                **base,
                "created_by": current_user_id or None,
                "created_at": now_text,
            }
            result = get_sb().table(REPORT_CONTEXT_TABLE).insert(json_safe(create_payload)).execute()
            saved = (getattr(result, "data", None) or [create_payload])[0]
        saved_payload = {**_default_context(safe_run_id, safe_experiment_id, safe_lang), **dict(saved), **local_only, "_storage_status": "supabase"}
        _write_local_context(saved_payload)
        _clear_cached_reports(safe_run_id, safe_lang)
        return saved_payload
    except Exception:
        fallback = {
            **_default_context(safe_run_id, safe_experiment_id, safe_lang),
            **base,
            "created_by": current_user_id,
            "created_at": now_text,
            "updated_at": now_text,
            **local_only,
            "_storage_status": "local_cache",
        }
        _write_local_context(fallback)
        _clear_cached_reports(safe_run_id, safe_lang)
        return fallback


def report_context_options() -> dict[str, tuple[str, ...]]:
    return {
        "purpose_key": PURPOSE_OPTIONS,
        "decision_under_consideration_key": DECISION_OPTIONS,
        "audience_key": AUDIENCE_OPTIONS,
    }


def report_context_completion(context: dict[str, Any]) -> dict[str, Any]:
    completed = sum(1 for field in REQUIRED_CONTEXT_FIELDS if _clean_text(context.get(field)))
    missing_fields = [field for field in REQUIRED_CONTEXT_FIELDS if not _clean_text(context.get(field))]
    return {
        "completed_fields": completed,
        "total_fields": len(REQUIRED_CONTEXT_FIELDS),
        "complete": completed == len(REQUIRED_CONTEXT_FIELDS),
        "missing_fields": missing_fields,
    }
