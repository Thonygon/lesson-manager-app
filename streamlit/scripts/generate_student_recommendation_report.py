from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import os
from pathlib import Path
import sys
import textwrap
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
from helpers.student_recommendation_ml import (  # noqa: E402
    build_report_profile_snapshot,
    build_student_recommendation_samples,
    summarize_student_recommendation_samples,
)
from services.ai_usage_service import log_ai_usage_event  # noqa: E402

def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _list_student_activity_ids(limit: int = 24) -> list[str]:
    counts: Counter[str] = Counter()
    try:
        practice_rows = (
            get_sb()
            .table("practice_sessions")
            .select("user_id")
            .order("created_at", desc=True)
            .limit(4000)
            .execute()
            .data
            or []
        )
        counts.update(str(row.get("user_id") or "").strip() for row in practice_rows if str(row.get("user_id") or "").strip())
    except Exception:
        pass
    try:
        assignment_rows = (
            get_sb()
            .table("teacher_assignments")
            .select("student_id")
            .order("updated_at", desc=True)
            .limit(4000)
            .execute()
            .data
            or []
        )
        counts.update(str(row.get("student_id") or "").strip() for row in assignment_rows if str(row.get("student_id") or "").strip())
    except Exception:
        pass
    return [student_id for student_id, _count in counts.most_common(limit)]


def _pick_student_id() -> str:
    ids = _list_student_activity_ids(limit=1)
    return ids[0] if ids else ""


def _empty_snapshot(scope: str) -> dict:
    return {
        "scope": scope,
        "practice_summary": {"rows": 0, "subjects": {}, "avg_score_pct": 0.0},
        "primary_subjects": [],
        "program_signals": {"subjects": set()},
    }


def _build_segment_recalibration_rows(samples: list[dict], base_blend_weight: float) -> list[dict]:
    by_subject: dict[str, list[dict]] = {}
    for sample in samples:
        subject = str(sample.get("subject") or "").strip()
        if not subject:
            continue
        by_subject.setdefault(subject, []).append(sample)

    rows: list[dict] = []
    for subject, subject_samples in by_subject.items():
        if len(subject_samples) < 4:
            continue
        diagnostics = summarize_student_recommendation_samples(subject_samples)
        positive_rate = float(diagnostics.get("positive_rate") or 0.0)
        f1 = float((diagnostics.get("metrics") or {}).get("f1") or 0.0)
        recalibrated_weight = _clamp(base_blend_weight * (0.9 + (0.25 * positive_rate) + (0.15 * f1)), 0.35, 0.8)
        rows.append(
            {
                "segment": subject,
                "sample_count": int(diagnostics.get("sample_count") or 0),
                "positive_rate": positive_rate,
                "f1": f1,
                "recommended_blend_weight": recalibrated_weight,
            }
        )
    rows.sort(key=lambda item: (-item["sample_count"], item["segment"]))
    return rows[:8]


def _load_single_student_project_data(student_id: str | None) -> dict:
    safe_student_id = str(student_id or "").strip() or _pick_student_id()
    if not safe_student_id:
        samples: list[dict] = []
        return {
            "mode": "live",
            "scope": "single_student",
            "student_id": "",
            "snapshot": _empty_snapshot("single_student"),
            "samples": samples,
            "diagnostics": summarize_student_recommendation_samples(samples),
        }
    try:
        snapshot = build_report_profile_snapshot(safe_student_id)
        samples = build_student_recommendation_samples(snapshot, student_id=safe_student_id)
        return {
            "mode": "live",
            "scope": "single_student",
            "student_id": safe_student_id,
            "snapshot": {**snapshot, "scope": "single_student"},
            "samples": samples,
            "diagnostics": summarize_student_recommendation_samples(samples),
        }
    except Exception:
        samples = []
        return {
            "mode": "live",
            "scope": "single_student",
            "student_id": safe_student_id,
            "snapshot": _empty_snapshot("single_student"),
            "samples": samples,
            "diagnostics": summarize_student_recommendation_samples(samples),
        }


def _load_multi_student_project_data(max_students: int = 12) -> dict:
    selected_students: list[dict] = []
    aggregate_samples: list[dict] = []
    for student_id in _list_student_activity_ids(limit=max_students * 4):
        try:
            snapshot = build_report_profile_snapshot(student_id)
            student_samples = build_student_recommendation_samples(snapshot, student_id=student_id)
        except Exception:
            continue
        if len(student_samples) < 4:
            continue
        aggregate_samples.extend(student_samples)
        selected_students.append(
            {
                "student_id": student_id,
                "sample_count": len(student_samples),
                "primary_subjects": list(snapshot.get("primary_subjects") or []),
                "avg_score_pct": float((snapshot.get("practice_summary") or {}).get("avg_score_pct") or 0.0),
            }
        )
        if len(selected_students) >= max_students:
            break

    diagnostics = summarize_student_recommendation_samples(aggregate_samples)
    segment_rows = _build_segment_recalibration_rows(aggregate_samples, float(diagnostics.get("blend_weight") or 0.42))
    subject_counter: Counter[str] = Counter()
    for sample in aggregate_samples:
        subject = str(sample.get("subject") or "").strip()
        if subject:
            subject_counter[subject] += 1
    return {
        "mode": "live",
        "scope": "multi_student",
        "student_id": "",
        "snapshot": {
            "scope": "multi_student",
            "student_count": len(selected_students),
            "students": selected_students,
            "practice_summary": {
                "rows": len(aggregate_samples),
                "subjects": dict(subject_counter),
                "avg_score_pct": 0.0,
            },
            "segment_rows": segment_rows,
        },
        "samples": aggregate_samples,
        "diagnostics": {**diagnostics, "segment_rows": segment_rows},
    }


def _load_project_data(student_id: str | None, scope: str = "single_student") -> dict:
    selected_scope = str(scope or "single_student").strip().lower()
    if selected_scope == "multi_student":
        return _load_multi_student_project_data()
    return _load_single_student_project_data(student_id)

def _report_meta() -> dict[str, object]:
    return {
        "model_name": {
            "en": "Student Recommendations",
            "es": "Recomendaciones para estudiantes",
            "tr": "Ogrenci onerileri",
        },
        "problem_single": {
            "en": "The problem belongs to EdTech and focuses on deciding which practice resource should be shown to a student so Classio can help that learner review weak areas or move forward to the next useful step.",
            "es": "El problema pertenece al area de EdTech y consiste en decidir que recurso de practica debe mostrarse a un alumno para que Classio le ayude a repasar debilidades o avanzar hacia el siguiente paso util.",
            "tr": "Problem EdTech alanina aittir ve Classio'nun ogrencinin zayif alanlari tekrar etmesine veya bir sonraki faydali adıma ilerlemesine yardim etmesi icin hangi alistirma kaynaginin gosterilmesi gerektigine odaklanir.",
        },
        "problem_multi": {
            "en": "The problem belongs to EdTech and focuses on learning from many active students so Classio can improve how it ranks practice resources by segment, subject and usage behaviour.",
            "es": "El problema pertenece al area de EdTech y consiste en aprender de muchos alumnos activos para que Classio mejore como ordena recursos de practica por segmento, materia y comportamiento de uso.",
            "tr": "Problem EdTech alanina aittir ve Classio'nun alistirma kaynaklarini segment, ders ve kullanim davranisina gore daha iyi siralayabilmesi icin birden fazla aktif ogrenciden ogrenmeye odaklanir.",
        },
        "tool_summary": {
            "en": "Python was selected inside Classio's production stack because it already has access to historical events, ranking logic and deployment paths, allowing the report to turn directly into product improvement.",
            "es": "Se selecciono Python dentro del stack productivo de Classio porque ya tiene acceso a eventos historicos, logica de ranking e integracion directa en producto.",
            "tr": "Python, Classio'nun uretim yigininda zaten tarihsel olaylara, siralama mantigina ve dagitim yoluna eristigi icin secildi; boylece rapor dogrudan urun iyilestirmesine donusebilir.",
        },
        "data_single": {
            "en": "This report uses real history from the most active student detected in Classio, combining practice sessions, teacher assignments and recommendation telemetry such as impressions and openings.",
            "es": "Este reporte utiliza historico real del estudiante con mayor actividad detectado en Classio, combinando sesiones de practica, asignaciones docentes y telemetria de recomendaciones como impresiones y aperturas.",
            "tr": "Bu rapor, Classio'da tespit edilen en aktif ogrencinin gercek gecmisini kullanir; alistirma oturumlari, ogretmen atamalari ve gosterim/acilis gibi onerı telemetrilerini birlestirir.",
        },
        "data_multi": {
            "en": "This report aggregates real histories from active students in Classio to evaluate the global recommendation layer and prepare segment-level recalibration.",
            "es": "Este reporte agrega historiales reales de estudiantes activos en Classio para evaluar la capa global del recomendador y preparar recalibracion por segmento.",
            "tr": "Bu rapor, aktif ogrencilerin gercek gecmislerini bir araya getirerek global onerı katmanini degerlendirir ve segment bazli yeniden kalibrasyon hazirlar.",
        },
        "preparation_summary": {
            "en": "Preparation included subject normalisation, status cleaning, binary target construction from outcomes and chronological ordering to separate training from evaluation.",
            "es": "La preparacion incluyo normalizacion de materias, limpieza de estados, construccion de targets binarios a partir de resultados y orden cronologico para separar entrenamiento y evaluacion.",
            "tr": "Hazirlik; ders normalizasyonu, durum temizligi, sonuc temelli ikili hedef olusturma ve egitim ile degerlendirmeyi ayirmak icin kronolojik siralama adimlarini icerdi.",
        },
        "config_summary": {
            "en": "The model is configured as a probabilistic linear classifier that blends existing recommendation heuristics with live evidence from assignments, outcomes and recommendation openings, using an approximate chronological 70/30 split.",
            "es": "El modelo se configura como un clasificador lineal probabilistico que mezcla las heuristicas existentes con evidencia real de asignaciones, resultados y aperturas de recomendaciones, usando un split cronologico aproximado 70/30.",
            "tr": "Model, mevcut onerı sezgilerini atamalar, sonuclar ve onerı acilislari gibi canli kanitlarla birlestiren olasiliksal dogrusal bir siniflandirici olarak yapilandirildi ve yaklasik kronolojik 70/30 bolunmesi kullanildi.",
        },
        "integration_summary": {
            "en": "In product, the evaluated output is blended into the recommendation ranking through a dynamic ML weight tied to observed historical quality.",
            "es": "En producto, la salida evaluada se mezcla dentro del ranking de recomendaciones mediante un peso ML dinamico ligado a la calidad historica observada.",
            "tr": "Urun icinde degerlendirilen cikti, gozlenen tarihsel kaliteye bagli dinamik bir ML agirligi ile onerı siralamasina karistirilir.",
        },
        "single_entity_label": {"en": "Student ID", "es": "Student ID", "tr": "Ogrenci ID"},
        "aggregate_entity_label": {"en": "Students aggregated", "es": "Estudiantes agregados", "tr": "Toplanan ogrenci sayisi"},
        "aggregate_count_key": "student_count",
        "entity_id_key": "student_id",
        "scope_kind": "student",
        "feature_labels": {
            "subject_in_program": {"en": "subject alignment with program", "es": "alineacion de materia con el programa", "tr": "program ile ders uyumu"},
            "level_fit": {"en": "level fit", "es": "ajuste de nivel", "tr": "seviye uyumu"},
            "stage_fit": {"en": "stage fit", "es": "ajuste de etapa", "tr": "asama uyumu"},
            "next_topic_overlap": {"en": "overlap with next topic", "es": "solapamiento con el siguiente tema", "tr": "siradaki konuyla ortusme"},
            "review_topic_overlap": {"en": "overlap with review topics", "es": "solapamiento con temas de repaso", "tr": "tekrar konulariyla ortusme"},
            "pending_topic_overlap": {"en": "overlap with pending topics", "es": "solapamiento con temas pendientes", "tr": "bekleyen konularla ortusme"},
            "topic_need": {"en": "topic need", "es": "necesidad del tema", "tr": "konu ihtiyaci"},
            "subject_need": {"en": "subject need", "es": "necesidad de materia", "tr": "ders ihtiyaci"},
            "exercise_need": {"en": "exercise need", "es": "necesidad de ejercicio", "tr": "egzersiz ihtiyaci"},
            "completion_fit": {"en": "completion fit", "es": "ajuste de completacion", "tr": "tamamlama uyumu"},
            "format_fit": {"en": "format fit", "es": "ajuste de formato", "tr": "format uyumu"},
            "explicit_topic_match": {"en": "explicit topic match", "es": "alineacion explicita del tema", "tr": "acik konu eslesmesi"},
            "explicit_topic_support": {"en": "explicit topic support", "es": "soporte explicito del tema", "tr": "acik konu destegi"},
            "direct_topic_link": {"en": "direct topic link", "es": "enlace directo con el tema", "tr": "dogrudan konu baglantisi"},
            "topic_kind_prior": {"en": "historical topic-kind prior", "es": "prior historico tema-tipo", "tr": "tarihsel konu-tur onceligi"},
            "topic_match_ambiguity": {"en": "topic-match ambiguity", "es": "ambiguedad de alineacion tematica", "tr": "konu eslesme belirsizligi"},
            "program_subject_fit": {"en": "program subject fit", "es": "ajuste de materia del programa", "tr": "program ders uyumu"},
            "program_type_fit": {"en": "program type fit", "es": "ajuste de tipo del programa", "tr": "program tur uyumu"},
        },
        "analysis_extras": [
            {
                "en": "The model is designed to complement the existing heuristic layer rather than replace it outright.",
                "es": "El modelo esta disenado para complementar la capa heuristica existente y aprender de su uso real, no para reemplazarla de forma abrupta.",
                "tr": "Model, mevcut sezgisel katmani dogrudan degistirmek yerine onu tamamlamak icin tasarlandi.",
            }
        ],
        "extra_limitations": [
            {
                "en": "Future iterations should connect recommendation openings with later completion and score lift so the target captures pedagogical impact even better.",
                "es": "Las siguientes iteraciones deberian conectar las aperturas de recomendaciones con finalizacion posterior y subida de nota para que el target capture mejor el impacto pedagogico.",
                "tr": "Sonraki iterasyonlar, hedefin pedagojik etkiyi daha iyi yansitmasi icin onerı acilislarini sonraki tamamlama ve puan artisi ile baglamalidir.",
            }
        ],
    }


def generate_report(output_dir: str | Path, student_id: str = "", scope: str = "single_student", lang: str = "") -> dict[str, object]:
    resolved_output_dir = Path(output_dir).resolve()
    resolved_output_dir.mkdir(parents=True, exist_ok=True)
    requested_scope = str(scope or "single_student").strip().lower() or "single_student"
    log_ai_usage_event(
        "student_diagnostic_report_ai",
        "requested",
        {
            "scope": requested_scope,
            "used_ai": False,
            "generation_mode": "template_only",
            "report_family": "live_diagnostics",
        },
    )
    try:
        data = _load_project_data(student_id, scope=scope)
        report_lang = resolve_report_language(preferred=lang)
        scope_key = str(data.get("scope") or "single_student")
        charts_dir = resolved_output_dir / f"assets_{scope_key}"
        charts = build_report_charts(data, charts_dir, report_lang)
        docx_path = resolved_output_dir / f"classio_ml_student_recommendation_report_{scope_key}.docx"
        summary_path = resolved_output_dir / f"classio_ml_student_recommendation_summary_{scope_key}.txt"
        write_classio_ml_report(docx_path, data, charts, _report_meta(), lang=report_lang)

        diagnostics = data["diagnostics"]
        metrics = diagnostics["metrics"]
        summary_path.write_text(
            "\n".join(
                [
                    f"mode={data['mode']}",
                    f"scope={scope_key}",
                    f"student_id={data['student_id']}",
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
        log_ai_usage_event(
            "student_diagnostic_report_ai",
            "success",
            {
                "scope": scope_key,
                "language": report_lang,
                "used_ai": False,
                "generation_mode": "template_only",
                "report_family": "live_diagnostics",
            },
        )
        return {
            "docx_path": str(docx_path),
            "summary_path": str(summary_path),
            "charts_dir": str(charts_dir),
            "mode": str(data["mode"]),
            "student_id": str(data["student_id"]),
            "lang": report_lang,
            "diagnostics": diagnostics,
        }
    except Exception as exc:
        log_ai_usage_event(
            "student_diagnostic_report_ai",
            "failed",
            {
                "scope": requested_scope,
                "used_ai": False,
                "generation_mode": "template_only",
                "report_family": "live_diagnostics",
                "error": str(exc),
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the Classio student recommendation ML project report.")
    parser.add_argument("--student-id", default="", help="Specific student id to analyze.")
    parser.add_argument("--output-dir", default=str(ROOT / "reports" / "student_recommendation_project"), help="Directory for docx and charts.")
    parser.add_argument("--scope", default="single_student", choices=["single_student", "multi_student"], help="Report scope.")
    args = parser.parse_args()
    result = generate_report(args.output_dir, student_id=args.student_id, scope=args.scope)
    print(result["docx_path"])


if __name__ == "__main__":
    main()
