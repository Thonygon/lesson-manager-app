from __future__ import annotations

import argparse
from collections import Counter
import os
from pathlib import Path
import sys
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python <3.11 compatibility
    try:
        import tomli as tomllib
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _bootstrap_supabase_env() -> None:
    candidates = [
        ROOT / ".streamlit" / "secrets.toml",
        ROOT / ".streamlit" / "secrets.toml.save",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        if tomllib is None:
            continue
        try:
            with candidate.open("rb") as fh:
                payload = tomllib.load(fh)
        except Exception:
            continue
        for key in ("SUPABASE_URL", "SUPABASE_KEY"):
            if not os.getenv(key) and payload.get(key):
                os.environ[key] = str(payload[key])


_bootstrap_supabase_env()

from core.database import get_sb  # noqa: E402
from helpers.ml_reporting import build_report_charts, resolve_report_language, write_classio_ml_report  # noqa: E402
from helpers.teacher_recommendation_ml import (  # noqa: E402
    build_teacher_objective_samples,
    build_teacher_recommendation_samples,
    summarize_teacher_objective_samples,
    build_teacher_report_profile_snapshot,
    summarize_teacher_recommendation_samples,
)
from scripts.generate_student_recommendation_report import _clamp  # noqa: E402


_FEATURE_LABELS = {
    "subject_demand": "demanda por materia",
    "kind_demand": "demanda por tipo de recurso",
    "topic_demand": "demanda temática",
    "kind_open_rate": "tasa de apertura por tipo de recurso",
    "source_open_rate": "tasa de apertura por fuente",
    "subject_open_rate": "tasa de apertura por materia",
    "topic_open_rate": "tasa de apertura por tema",
    "source_own": "preferencia por materiales propios",
    "topic_reference_present": "presencia de referencia temática explícita",
    "event_weight": "peso histórico del evento",
    "exact_topic_match": "coincidencia exacta con el tema",
    "exact_topic_support": "soporte temático complementario",
    "direct_topic_link": "enlace directo con el tema",
    "topic_kind_prior": "prior histórico por tipo-tema",
    "topic_match_ambiguity": "ambigüedad de coincidencia temática",
    "kind_plan": "tipo plan",
    "kind_worksheet": "tipo worksheet",
    "kind_exam": "tipo examen",
    "kind_video": "tipo video",
    "bucket_next_topic": "bucket next topic",
    "bucket_review": "bucket review",
    "bucket_pending_gap": "bucket pending gap",
    "focus_needs_practice": "focus needs practice",
    "focus_reteach": "focus reteach",
    "focus_reinforce": "focus reinforce",
    "focus_stretch": "focus stretch",
}


def _list_teacher_activity_ids(limit: int = 24) -> list[str]:
    counts: Counter[str] = Counter()
    try:
        recommendation_rows = (
            get_sb()
            .table("learning_program_recommendation_events")
            .select("teacher_id")
            .order("created_at", desc=True)
            .limit(4000)
            .execute()
            .data
            or []
        )
        counts.update(str(row.get("teacher_id") or "").strip() for row in recommendation_rows if str(row.get("teacher_id") or "").strip())
    except Exception:
        pass
    try:
        activity_rows = (
            get_sb()
            .table("user_activity_log")
            .select("user_id")
            .in_("activity_type", ["teacher_material_impression", "teacher_material_open"])
            .order("created_at", desc=True)
            .limit(4000)
            .execute()
            .data
            or []
        )
        counts.update(str(row.get("user_id") or "").strip() for row in activity_rows if str(row.get("user_id") or "").strip())
    except Exception:
        pass
    try:
        assignment_rows = (
            get_sb()
            .table("teacher_assignments")
            .select("teacher_id")
            .order("updated_at", desc=True)
            .limit(4000)
            .execute()
            .data
            or []
        )
        counts.update(str(row.get("teacher_id") or "").strip() for row in assignment_rows if str(row.get("teacher_id") or "").strip())
    except Exception:
        pass
    return [teacher_id for teacher_id, _count in counts.most_common(limit)]


def _pick_teacher_id() -> str:
    ids = _list_teacher_activity_ids(limit=1)
    return ids[0] if ids else ""


def _empty_snapshot(scope: str) -> dict:
    return {
        "scope": scope,
        "top_subjects": [],
        "recommendation_summary": {"rows": 0, "kinds": {}, "buckets": {}},
        "material_activity_summary": {"rows": 0, "activity_types": {}},
    }


def _build_segment_recalibration_rows(samples: list[dict], base_blend_weight: float) -> list[dict]:
    by_kind: dict[str, list[dict]] = {}
    for sample in samples:
        kind = str(sample.get("kind") or "").strip()
        if not kind:
            continue
        by_kind.setdefault(kind, []).append(sample)

    rows: list[dict] = []
    for kind, kind_samples in by_kind.items():
        if len(kind_samples) < 4:
            continue
        diagnostics = summarize_teacher_recommendation_samples(kind_samples)
        positive_rate = float(diagnostics.get("positive_rate") or 0.0)
        f1 = float((diagnostics.get("metrics") or {}).get("f1") or 0.0)
        recalibrated_weight = _clamp(base_blend_weight * (0.9 + (0.25 * positive_rate) + (0.15 * f1)), 0.35, 0.8)
        rows.append(
            {
                "segment": kind,
                "sample_count": int(diagnostics.get("sample_count") or 0),
                "positive_rate": positive_rate,
                "f1": f1,
                "recommended_blend_weight": recalibrated_weight,
            }
        )
    rows.sort(key=lambda item: (-item["sample_count"], item["segment"]))
    return rows[:8]


def _load_single_teacher_project_data(teacher_id: str | None) -> dict:
    safe_teacher_id = str(teacher_id or "").strip() or _pick_teacher_id()
    if not safe_teacher_id:
        samples: list[dict] = []
        return {
            "mode": "live",
            "scope": "single_teacher",
            "teacher_id": "",
            "snapshot": _empty_snapshot("single_teacher"),
            "samples": samples,
            "diagnostics": summarize_teacher_recommendation_samples(samples),
        }
    try:
        snapshot = build_teacher_report_profile_snapshot(safe_teacher_id)
        samples = build_teacher_recommendation_samples(snapshot, teacher_id=safe_teacher_id)
        objective_samples = build_teacher_objective_samples(safe_teacher_id)
        objective_diagnostics = summarize_teacher_objective_samples(objective_samples)
        diagnostics = summarize_teacher_recommendation_samples(samples)
        diagnostics["objective_diagnostics"] = objective_diagnostics
        return {
            "mode": "live",
            "scope": "single_teacher",
            "teacher_id": safe_teacher_id,
            "snapshot": {**snapshot, "scope": "single_teacher"},
            "samples": samples,
            "diagnostics": diagnostics,
        }
    except Exception:
        samples = []
        return {
            "mode": "live",
            "scope": "single_teacher",
            "teacher_id": safe_teacher_id,
            "snapshot": _empty_snapshot("single_teacher"),
            "samples": samples,
            "diagnostics": summarize_teacher_recommendation_samples(samples),
        }


def _load_multi_teacher_project_data(max_teachers: int = 12) -> dict:
    selected_teachers: list[dict] = []
    aggregate_samples: list[dict] = []
    aggregate_objective_samples: list[dict] = []
    subject_counter: Counter[str] = Counter()
    for teacher_id in _list_teacher_activity_ids(limit=max_teachers * 4):
        try:
            snapshot = build_teacher_report_profile_snapshot(teacher_id)
            teacher_samples = build_teacher_recommendation_samples(snapshot, teacher_id=teacher_id)
            teacher_objective_samples = build_teacher_objective_samples(teacher_id)
        except Exception:
            continue
        if len(teacher_samples) < 4:
            continue
        aggregate_samples.extend(teacher_samples)
        aggregate_objective_samples.extend(teacher_objective_samples)
        for subject in snapshot.get("top_subjects") or []:
            if str(subject or "").strip():
                subject_counter[str(subject)] += 1
        selected_teachers.append(
            {
                "teacher_id": teacher_id,
                "sample_count": len(teacher_samples),
                "top_subjects": list(snapshot.get("top_subjects") or []),
                "recommendation_rows": int((snapshot.get("recommendation_summary") or {}).get("rows") or 0),
            }
        )
        if len(selected_teachers) >= max_teachers:
            break

    diagnostics = summarize_teacher_recommendation_samples(aggregate_samples)
    diagnostics["objective_diagnostics"] = summarize_teacher_objective_samples(aggregate_objective_samples)
    segment_rows = _build_segment_recalibration_rows(aggregate_samples, float(diagnostics.get("blend_weight") or 0.42))
    return {
        "mode": "live",
        "scope": "multi_teacher",
        "teacher_id": "",
        "snapshot": {
            "scope": "multi_teacher",
            "teacher_count": len(selected_teachers),
            "teachers": selected_teachers,
            "top_subjects": [subject for subject, _count in subject_counter.most_common(6)],
            "recommendation_summary": {
                "rows": len(aggregate_samples),
                "kinds": dict(Counter(str(sample.get("kind") or "") for sample in aggregate_samples if str(sample.get("kind") or "").strip())),
                "buckets": {},
            },
            "material_activity_summary": {"rows": 0, "activity_types": {}},
            "segment_rows": segment_rows,
        },
        "samples": aggregate_samples,
        "diagnostics": {**diagnostics, "segment_rows": segment_rows},
    }


def _load_project_data(teacher_id: str | None, scope: str = "single_teacher") -> dict:
    selected_scope = str(scope or "single_teacher").strip().lower()
    if selected_scope == "multi_teacher":
        return _load_multi_teacher_project_data()
    return _load_single_teacher_project_data(teacher_id)


def _report_meta() -> dict[str, object]:
    return {
        "model_name": {
            "en": "Teacher Recommendations",
            "es": "Recomendaciones para profesor",
            "tr": "Ogretmen onerileri",
        },
        "problem_single": {
            "en": "The problem belongs to EdTech and focuses on deciding what a teacher most likely needs to teach next: the next topic, a review topic or a pending gap, before Classio ranks the supporting resources.",
            "es": "El problema pertenece al area de EdTech y consiste en decidir que necesita enseñar antes un profesor: el siguiente tema, un tema de repaso o un hueco pendiente, antes de que Classio ordene los recursos de apoyo.",
            "tr": "Problem EdTech alanina aittir ve Classio'nun destekleyici kaynaklari siralamadan once bir ogretmenin sirada ne ogretmesi gerektigine karar vermeye odaklanir: sonraki konu, tekrar konusu veya bekleyen bir bosluk.",
        },
        "problem_multi": {
            "en": "The problem belongs to EdTech and focuses on learning across active teachers whether Classio is choosing the right pedagogical objective and then attaching the right resource mix to that decision.",
            "es": "El problema pertenece al area de EdTech y consiste en aprender entre docentes activos si Classio esta eligiendo el objetivo pedagogico correcto y despues asociando el mix adecuado de recursos a esa decision.",
            "tr": "Problem EdTech alanina aittir ve aktif ogretmenler genelinde Classio'nun dogru pedagojik hedefi secip secmedigini ve sonra bu karara dogru kaynak karmasini baglayip baglamadigini ogrenmeye odaklanir.",
        },
        "tool_summary": {
            "en": "Python was selected inside Classio's production stack because the product already stores recommendation events, activity signals and ranking logic that can be evaluated without leaving the platform.",
            "es": "Se selecciono Python dentro del stack productivo de Classio porque el producto ya almacena eventos de recomendacion, senales de actividad y logica de ranking que pueden evaluarse sin salir de la plataforma.",
            "tr": "Python, urunun zaten onerı olaylarini, aktivite sinyallerini ve siralama mantigini platformdan cikmadan degerlendirmeye imkan verecek sekilde depolamasi nedeniyle Classio'nun uretim yigininda secildi.",
        },
        "data_single": {
            "en": "This report uses real history from the most active teacher detected in Classio, combining recommendation events, assignment outcomes and material impressions/openings tied to the teacher workflow.",
            "es": "Este reporte utiliza historico real del docente con mayor actividad detectado en Classio, combinando eventos de recomendacion, resultados de asignacion e impresiones/aperturas de materiales vinculadas al flujo docente.",
            "tr": "Bu rapor, Classio'da tespit edilen en aktif ogretmenin gercek gecmisini kullanir; ogretmen akisina bagli onerı olaylarini, atama sonuclarini ve materyal gosterim/acilislarini birlestirir.",
        },
        "data_multi": {
            "en": "This report aggregates real histories from active teachers in Classio to evaluate the global teacher recommendation layer and compare behaviour across resource segments.",
            "es": "Este reporte agrega historiales reales de docentes activos en Classio para evaluar la capa global de recomendaciones para profesor y comparar comportamiento entre segmentos de recursos.",
            "tr": "Bu rapor, aktif ogretmenlerin gercek gecmislerini bir araya getirerek global ogretmen onerı katmanini degerlendirir ve kaynak segmentleri arasindaki davranisi karsilastirir.",
        },
        "preparation_summary": {
            "en": "Preparation included event cleanup, resource-type normalisation, binary target construction from observed actions and chronological ordering to keep validation future-facing.",
            "es": "La preparacion incluyo limpieza de eventos, normalizacion de tipos de recurso, construccion de targets binarios a partir de acciones observadas y orden cronologico para mantener una validacion orientada al futuro.",
            "tr": "Hazirlik; olay temizligi, kaynak turu normalizasyonu, gozlenen aksiyonlardan ikili hedef olusturma ve dogrulamayi gelecege donuk tutmak icin kronolojik siralama adimlarini icerdi.",
        },
        "config_summary": {
            "en": "The model is configured as a two-layer probabilistic classifier: first it scores the pedagogical objective (next topic, review or pending gap), then it evaluates the resource mix attached to that objective, using an approximate chronological 70/30 split.",
            "es": "El modelo se configura como un clasificador probabilistico de dos capas: primero puntua el objetivo pedagogico (siguiente tema, repaso o hueco pendiente) y despues evalua el mix de recursos asociado a ese objetivo, usando un split cronologico aproximado 70/30.",
            "tr": "Model iki katmanli olasiliksal bir siniflandirici olarak yapilandirildi: once pedagojik hedefi puanlar (siradaki konu, tekrar veya bekleyen bosluk), sonra bu hedefe bagli kaynak karmasini degerlendirir; yaklasik kronolojik 70/30 bolunmesi kullanilir.",
        },
        "integration_summary": {
            "en": "In product, the objective score now helps order live teacher recommendations before the resource scorer chooses the best supporting material, so Classio can learn both what to suggest and how to package it.",
            "es": "En producto, la puntuacion del objetivo ya ayuda a ordenar las recomendaciones vivas del profesor antes de que el ranker de recursos elija el mejor material de apoyo, de modo que Classio aprenda tanto que sugerir como con que recurso hacerlo.",
            "tr": "Urun icinde hedef puani artik canli ogretmen onerilerini siralamaya yardim eder; daha sonra kaynak siralayici en uygun destek materyalini secer. Boylece Classio hem ne onerecegini hem de bunu hangi kaynakla sunacagini ogrenebilir.",
        },
        "single_entity_label": {"en": "Teacher ID", "es": "Teacher ID", "tr": "Ogretmen ID"},
        "aggregate_entity_label": {"en": "Teachers aggregated", "es": "Docentes agregados", "tr": "Toplanan ogretmen sayisi"},
        "aggregate_count_key": "teacher_count",
        "entity_id_key": "teacher_id",
        "scope_kind": "teacher",
        "feature_labels": _FEATURE_LABELS,
        "analysis_extras": [
            {
                "en": "The multi-teacher view is especially useful to compare whether one resource format dominates adoption more than the others.",
                "es": "La vista multi-teacher es especialmente util para comparar si Classio esta acertando mas al elegir el objetivo pedagogico que al elegir el formato de recurso, o al reves.",
                "tr": "Multi-teacher gorunumu, belirli bir kaynak formatinin digerlerine gore benimsemeyi daha fazla yonlendirip yonlendirmedigini karsilastirmak icin ozellikle faydalidir.",
            }
        ],
        "extra_limitations": [
            {
                "en": "Future iterations should connect the selected objective with lesson completion and later student progress so the system can validate not only engagement but pedagogical payoff.",
                "es": "Las siguientes iteraciones deberian conectar el objetivo elegido con el cierre real de la clase y el progreso posterior del alumno para validar no solo engagement sino retorno pedagogico.",
                "tr": "Sonraki iterasyonlar, yalnizca etkilesimi degil pedagojik getiriyi de dogrulamak icin secilen hedefi ders tamamlama ve sonraki ogrenci ilerlemesiyle baglamalidir.",
            }
        ],
    }


def generate_report(output_dir: str | Path, teacher_id: str = "", scope: str = "single_teacher", lang: str = "") -> dict[str, object]:
    resolved_output_dir = Path(output_dir).resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    data = _load_project_data(teacher_id, scope=scope)
    report_lang = resolve_report_language(preferred=lang)
    scope_key = str(data.get("scope") or "single_teacher")
    charts_dir = resolved_output_dir / f"assets_{scope_key}"
    charts = build_report_charts(data, charts_dir, report_lang)
    docx_path = resolved_output_dir / f"classio_ml_teacher_recommendation_report_{scope_key}.docx"
    summary_path = resolved_output_dir / f"classio_ml_teacher_recommendation_summary_{scope_key}.txt"
    write_classio_ml_report(docx_path, data, charts, _report_meta(), lang=report_lang)

    diagnostics = data["diagnostics"]
    metrics = diagnostics["metrics"]
    summary_path.write_text(
        "\n".join(
            [
                f"mode={data['mode']}",
                f"scope={scope_key}",
                f"teacher_id={data['teacher_id']}",
                f"samples={diagnostics['sample_count']}",
                f"train={diagnostics['train_count']}",
                f"test={diagnostics['test_count']}",
                f"accuracy={metrics.get('accuracy', 0.0):.4f}",
                f"precision={metrics.get('precision', 0.0):.4f}",
                f"recall={metrics.get('recall', 0.0):.4f}",
                f"f1={metrics.get('f1', 0.0):.4f}",
                f"roc_auc={metrics.get('roc_auc', 0.0):.4f}",
                f"blend_weight={diagnostics.get('blend_weight', 0.0):.4f}",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "docx_path": str(docx_path),
        "summary_path": str(summary_path),
        "charts_dir": str(charts_dir),
        "mode": str(data["mode"]),
        "teacher_id": str(data["teacher_id"]),
        "lang": report_lang,
        "diagnostics": diagnostics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Classio teacher recommendation ML report.")
    parser.add_argument("--teacher-id", default="", help="Specific teacher id to analyze.")
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "teacher_recommendation_project"), help="Directory for docx and charts.")
    parser.add_argument("--scope", default="single_teacher", choices=["single_teacher", "multi_teacher"], help="Report scope.")
    args = parser.parse_args()
    result = generate_report(args.output_dir, teacher_id=args.teacher_id, scope=args.scope)
    print(result["docx_path"])


if __name__ == "__main__":
    main()
