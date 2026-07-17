from __future__ import annotations

from datetime import datetime
from io import BytesIO
import hashlib
import json
from pathlib import Path
from typing import Any
from zipfile import BadZipFile, ZipFile

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from core.i18n import t
from services import eic_service
from services.authorization_service import CAPABILITY_VIEW_TECHNICAL_ARTIFACTS
from services.eic_display_service import (
    get_business_action_display,
    get_component_display_name,
    get_component_type_display,
    get_evidence_display,
    get_integrity_status_display,
    get_model_comparison_column_display,
    get_model_comparison_value_display,
    get_model_name_display,
    get_model_result_status_display,
    get_maturity_display,
    get_report_type_display,
    get_run_status_display,
)
from services.eic_report_charts import build_report_charts
from services.ml_experiment_service import FINAL_VALIDATED_RUN_STATES, list_run_artifacts


REPORT_ROOT = Path("reports") / "ml_architecture" / "eic_reports"
REPORT_TYPES = ("experiment_docx", "executive_docx", "academic_docx", "technical_docx")
EXPERIMENT_REPORT_TEMPLATE_VERSION = 4
PAGE_WIDTH_PORTRAIT = 6.9
PAGE_WIDTH_LANDSCAPE = 9.4
TABLE_WIDTH_GUTTER = 0.18
CLASSIO_BLUE = RGBColor(31, 58, 95)
CLASSIO_TEAL = RGBColor(23, 128, 126)
CLASSIO_GOLD = RGBColor(183, 121, 31)
CLASSIO_RED = RGBColor(197, 48, 48)
MUTED = RGBColor(90, 98, 111)
TABLE_HEADER_FILL = "EAF0F7"
NOTE_FILL = "F6F8FB"


_COPY: dict[str, dict[str, str]] = {
    "en": {
        "validated": "Validated evidence",
        "confidential": "Validated internal report",
        "cover_kicker": "Classio Educational Intelligence Center",
        "cover_status": "Validation status: {value}",
        "cover_generated": "Generated on {value}",
        "cover_run": "Validated run: {value}",
        "cover_fingerprint": "Dataset fingerprint: {value}",
        "appendix": "Appendix",
        "source_note": "Source: validated stored run artifacts only.",
        "figure_note": "Interpretation uses stored metrics and predictions; no model retraining was performed.",
        "yes": "Yes",
        "no": "No",
        "not_available": "Not available",
        "executive_report_name": "Executive Business Report",
        "academic_report_name": "Findings Interpretation Report",
        "technical_report_name": "Technical Data Science Report",
        "meta_field": "Field",
        "meta_value": "Value",
        "summary_snapshot": "Validated evidence snapshot",
        "what_was_evaluated": "What was evaluated",
        "what_evidence_showed": "What the evidence showed",
        "replacement_question": "Can the heuristic system be replaced",
        "leadership_action": "What leadership should do now",
        "missing_evidence": "What evidence is still missing",
        "portfolio_summary": "Intelligence portfolio summary",
        "data_feedback_health": "Data and feedback health",
        "business_risks": "Business risks",
        "prioritized_actions": "Prioritized actions",
        "roadmap": "Roadmap and next review milestone",
        "run_metadata": "Concise run metadata",
        "exec_findings": "Leadership findings",
        "exec_intro": "This report translates the latest validated EIC evidence into business decisions for Classio leadership.",
        "exec_replace_hold": "The current heuristic assignment and recommendation logic should remain in place. The validated supervised experiment is informative, but it does not yet establish a production-grade replacement.",
        "exec_missing": "Evidence is still missing across teacher diversity, telemetry completeness, and repeated validated runs with broader operational coverage.",
        "academic_abstract": "Executive abstract",
        "company_context": "Company and EdTech context",
        "problem_statement": "Problem statement",
        "solution_statement": "Solution statement",
        "smart_objective": "SMART objectives",
        "supervised_formulation": "Supervised-learning formulation",
        "dataset_sources": "Dataset and data sources",
        "data_preparation": "Data preparation",
        "feature_selection": "Variable and feature selection",
        "target_construction": "Target construction",
        "methodology": "Experimental methodology",
        "models_evaluated": "Models evaluated",
        "evaluation_metrics": "Evaluation metrics",
        "results": "Results",
        "comparative_analysis": "Comparative analysis",
        "conclusions": "Conclusions",
        "implementation": "Business implementation implications",
        "limitations": "Limitations",
        "future_work": "Future work",
        "references": "References",
        "technical_metadata": "Document control and metadata",
        "experiment_definition": "Experiment definition",
        "source_logic": "Source tables and extraction logic",
        "dataset_accounting": "Dataset accounting",
        "label_reconciliation": "Label construction and reconciliation",
        "leakage_controls": "Leakage controls",
        "feature_health": "Feature schema and feature health",
        "preprocessing": "Preprocessing pipelines",
        "cv_section": "Chronological split and cross-validation",
        "model_configuration": "Model configurations",
        "baseline_results": "Baseline and comparison results",
        "threshold_analysis": "Threshold analysis",
        "roc_analysis": "ROC analysis",
        "pr_analysis": "Precision-recall analysis",
        "calibration_analysis": "Calibration analysis",
        "error_analysis": "Error analysis",
        "uncertainty": "Uncertainty and confidence intervals",
        "runtime": "Runtime and resource performance",
        "integrity": "Integrity-review results",
        "reproducibility": "Reproducibility",
        "deployment": "Deployment and shadow-testing recommendation",
        "artifact_manifest": "Artifact manifest",
        "section_note": "Interpretation",
        "academic_conclusion": "The comparison did not establish a statistically robust overall winner. Random Forest led several stored evaluation criteria, but the small holdout and single-teacher sample prevent a production-level conclusion.",
        "technical_conclusion": "The validated review concludes that this run is suitable as a technical evidence package, but not as a deployment decision.",
        "artifact_name": "Artifact",
        "artifact_purpose": "Purpose",
        "artifact_format": "Format",
        "artifact_checksum": "Checksum",
        "artifact_availability": "Availability",
        "artifact_filename": "Stored filename",
        "system": "System",
        "current_approach": "Current approach",
        "business_use": "Business use",
        "evidence": "Evidence",
        "recommended_action": "Recommended action",
        "priority": "Priority",
        "component": "Component",
        "impact": "Business impact",
        "owner": "Owner",
        "review_trigger": "Review trigger",
        "model": "Model",
        "result": "Result",
        "interpretation": "Interpretation",
        "caption_portfolio": "Portfolio table summarizing the systems currently discussed in the admin intelligence workspace.",
        "caption_actions": "Prioritized decisions table aligned to the admin leadership workflow.",
        "caption_models": "Readable comparison of stored supervised models using the validated run artifacts.",
        "caption_feature_health": "Feature-health table using the stored audit and review output.",
        "caption_manifest": "Artifact manifest summarizing the technical evidence package without exposing repository paths.",
        "visual_qa_passed": "Prepared for visual QA render",
    },
    "es": {
        "validated": "Evidencia validada",
        "confidential": "Informe interno validado",
        "cover_kicker": "Centro de Inteligencia Educativa de Classio",
        "cover_status": "Estado de validación: {value}",
        "cover_generated": "Generado el {value}",
        "cover_run": "Ejecución validada: {value}",
        "cover_fingerprint": "Huella del conjunto de datos: {value}",
        "appendix": "Apéndice",
        "source_note": "Fuente: solo artefactos validados y almacenados.",
        "figure_note": "La interpretación usa métricas y predicciones almacenadas; no se volvió a entrenar ningún modelo.",
        "yes": "Sí",
        "no": "No",
        "not_available": "No disponible",
        "executive_report_name": "Informe Ejecutivo de Negocio",
        "academic_report_name": "Informe de Interpretación de Hallazgos",
        "technical_report_name": "Informe Técnico de Ciencia de Datos",
        "meta_field": "Campo",
        "meta_value": "Valor",
        "summary_snapshot": "Resumen de evidencia validada",
        "what_was_evaluated": "Qué se evaluó",
        "what_evidence_showed": "Qué mostró la evidencia",
        "replacement_question": "Si el sistema heurístico puede sustituirse",
        "leadership_action": "Qué debe hacer ahora el liderazgo",
        "missing_evidence": "Qué evidencia sigue faltando",
        "portfolio_summary": "Resumen del portafolio de inteligencia",
        "data_feedback_health": "Salud de datos y retroalimentación",
        "business_risks": "Riesgos de negocio",
        "prioritized_actions": "Acciones priorizadas",
        "roadmap": "Hoja de ruta y próximo hito de revisión",
        "run_metadata": "Metadatos resumidos de la ejecución",
        "exec_findings": "Hallazgos para liderazgo",
        "exec_intro": "Este informe traduce la evidencia EIC validada más reciente en decisiones de negocio para el liderazgo de Classio.",
        "exec_replace_hold": "La lógica heurística actual para asignaciones y recomendaciones debe mantenerse. El experimento supervisado validado aporta señales útiles, pero no demuestra aún un reemplazo apto para producción.",
        "exec_missing": "Aún falta evidencia en diversidad docente, completitud de telemetría y repeticiones validadas con mayor cobertura operativa.",
        "academic_abstract": "Resumen ejecutivo",
        "company_context": "Contexto de la empresa y EdTech",
        "problem_statement": "Planteamiento del problema",
        "solution_statement": "Planteamiento de la solución",
        "smart_objective": "Objetivos SMART",
        "supervised_formulation": "Formulación de aprendizaje supervisado",
        "dataset_sources": "Conjunto de datos y fuentes",
        "data_preparation": "Preparación de datos",
        "feature_selection": "Selección de variables y características",
        "target_construction": "Construcción del objetivo",
        "methodology": "Metodología experimental",
        "models_evaluated": "Modelos evaluados",
        "evaluation_metrics": "Métricas de evaluación",
        "results": "Resultados",
        "comparative_analysis": "Análisis comparativo",
        "conclusions": "Conclusiones",
        "implementation": "Implicaciones de implementación",
        "limitations": "Limitaciones",
        "future_work": "Trabajo futuro",
        "references": "Referencias",
        "technical_metadata": "Control documental y metadatos",
        "experiment_definition": "Definición del experimento",
        "source_logic": "Tablas fuente y lógica de extracción",
        "dataset_accounting": "Contabilidad del conjunto de datos",
        "label_reconciliation": "Construcción y conciliación de etiquetas",
        "leakage_controls": "Controles contra fuga de información",
        "feature_health": "Esquema y salud de variables",
        "preprocessing": "Pipelines de preprocesamiento",
        "cv_section": "Corte cronológico y validación cruzada",
        "model_configuration": "Configuraciones de modelo",
        "baseline_results": "Resultados base y comparación",
        "threshold_analysis": "Análisis de umbrales",
        "roc_analysis": "Análisis ROC",
        "pr_analysis": "Análisis precision-recall",
        "calibration_analysis": "Análisis de calibración",
        "error_analysis": "Análisis de errores",
        "uncertainty": "Incertidumbre e intervalos de confianza",
        "runtime": "Rendimiento temporal y recursos",
        "integrity": "Resultados de la revisión de integridad",
        "reproducibility": "Reproducibilidad",
        "deployment": "Recomendación de despliegue y shadow testing",
        "artifact_manifest": "Manifiesto de artefactos",
        "section_note": "Interpretación",
        "academic_conclusion": "La comparación no estableció un ganador global estadísticamente robusto. Random Forest lideró varios criterios almacenados, pero el holdout pequeño y la muestra de un solo docente impiden una conclusión apta para producción.",
        "technical_conclusion": "La revisión validada concluye que esta ejecución sirve como paquete de evidencia técnica, pero no como decisión de despliegue.",
        "artifact_name": "Artefacto",
        "artifact_purpose": "Propósito",
        "artifact_format": "Formato",
        "artifact_checksum": "Checksum",
        "artifact_availability": "Disponibilidad",
        "artifact_filename": "Nombre almacenado",
        "system": "Sistema",
        "current_approach": "Enfoque actual",
        "business_use": "Uso de negocio",
        "evidence": "Evidencia",
        "recommended_action": "Acción recomendada",
        "priority": "Prioridad",
        "component": "Componente",
        "impact": "Impacto de negocio",
        "owner": "Responsable",
        "review_trigger": "Disparador de revisión",
        "model": "Modelo",
        "result": "Resultado",
        "interpretation": "Interpretación",
        "caption_portfolio": "Tabla del portafolio con los sistemas discutidos en el espacio de inteligencia del panel de administración.",
        "caption_actions": "Tabla de decisiones priorizadas alineada con el flujo ejecutivo del panel.",
        "caption_models": "Comparación legible de los modelos supervisados almacenados en la ejecución validada.",
        "caption_feature_health": "Tabla de salud de variables basada en la auditoría y la revisión almacenadas.",
        "caption_manifest": "Manifiesto de artefactos del paquete técnico sin exponer rutas del repositorio.",
        "visual_qa_passed": "Preparado para la revisión visual renderizada",
    },
    "tr": {
        "validated": "Doğrulanmış kanıt",
        "confidential": "Doğrulanmış dahili rapor",
        "cover_kicker": "Classio Eğitsel Zekâ Merkezi",
        "cover_status": "Doğrulama durumu: {value}",
        "cover_generated": "{value} tarihinde üretildi",
        "cover_run": "Doğrulanmış çalışma: {value}",
        "cover_fingerprint": "Veri kümesi parmak izi: {value}",
        "appendix": "Ek",
        "source_note": "Kaynak: yalnızca doğrulanmış ve saklanan artefaktlar.",
        "figure_note": "Yorum, saklanan metriklere ve tahminlere dayanır; model yeniden eğitilmedi.",
        "yes": "Evet",
        "no": "Hayır",
        "not_available": "Mevcut değil",
        "executive_report_name": "Yönetici İş Raporu",
        "academic_report_name": "Bulgular Yorumlama Raporu",
        "technical_report_name": "Teknik Veri Bilimi Raporu",
        "meta_field": "Alan",
        "meta_value": "Değer",
        "summary_snapshot": "Doğrulanmış kanıt özeti",
        "what_was_evaluated": "Ne değerlendirildi",
        "what_evidence_showed": "Kanıt ne gösterdi",
        "replacement_question": "Sezgisel sistemin yerini alıp alamayacağı",
        "leadership_action": "Liderliğin şimdi ne yapması gerektiği",
        "missing_evidence": "Hangi kanıtların hâlâ eksik olduğu",
        "portfolio_summary": "Zekâ portföyü özeti",
        "data_feedback_health": "Veri ve geri bildirim sağlığı",
        "business_risks": "İş riskleri",
        "prioritized_actions": "Öncelikli eylemler",
        "roadmap": "Yol haritası ve sonraki inceleme kilometre taşı",
        "run_metadata": "Kısa çalışma meta verisi",
        "exec_findings": "Liderlik bulguları",
        "exec_intro": "Bu rapor, en son doğrulanmış EIC kanıtını Classio liderliği için iş kararlarına dönüştürür.",
        "exec_replace_hold": "Mevcut sezgisel atama ve öneri mantığı korunmalıdır. Doğrulanmış denetimli deney yararlı bir sinyal sunuyor, ancak üretim düzeyinde bir ikameyi henüz kanıtlamıyor.",
        "exec_missing": "Öğretmen çeşitliliği, telemetri bütünlüğü ve daha geniş operasyonel kapsamda tekrarlanan doğrulanmış çalışmalar açısından kanıt hâlâ eksik.",
        "academic_abstract": "Yönetici özeti",
        "company_context": "Şirket ve EdTech bağlamı",
        "problem_statement": "Problemin tanımı",
        "solution_statement": "Çözüm yaklaşımı",
        "smart_objective": "SMART hedefleri",
        "supervised_formulation": "Denetimli öğrenme formülasyonu",
        "dataset_sources": "Veri kümesi ve kaynaklar",
        "data_preparation": "Veri hazırlığı",
        "feature_selection": "Değişken ve özellik seçimi",
        "target_construction": "Hedef oluşturma",
        "methodology": "Deneysel metodoloji",
        "models_evaluated": "Değerlendirilen modeller",
        "evaluation_metrics": "Değerlendirme metrikleri",
        "results": "Sonuçlar",
        "comparative_analysis": "Karşılaştırmalı analiz",
        "conclusions": "Sonuçlar",
        "implementation": "İş uygulaması etkileri",
        "limitations": "Sınırlamalar",
        "future_work": "Gelecek çalışmalar",
        "references": "Kaynaklar",
        "technical_metadata": "Belge kontrolü ve meta veriler",
        "experiment_definition": "Deney tanımı",
        "source_logic": "Kaynak tablolar ve çıkarım mantığı",
        "dataset_accounting": "Veri kümesi muhasebesi",
        "label_reconciliation": "Etiket oluşturma ve uzlaştırma",
        "leakage_controls": "Sızıntı kontrolleri",
        "feature_health": "Özellik şeması ve sağlık durumu",
        "preprocessing": "Ön işleme hatları",
        "cv_section": "Kronolojik ayrım ve çapraz doğrulama",
        "model_configuration": "Model yapılandırmaları",
        "baseline_results": "Temel ve karşılaştırma sonuçları",
        "threshold_analysis": "Eşik analizi",
        "roc_analysis": "ROC analizi",
        "pr_analysis": "Precision-recall analizi",
        "calibration_analysis": "Kalibrasyon analizi",
        "error_analysis": "Hata analizi",
        "uncertainty": "Belirsizlik ve güven aralıkları",
        "runtime": "Çalışma süresi ve kaynak performansı",
        "integrity": "Bütünlük inceleme sonuçları",
        "reproducibility": "Yeniden üretilebilirlik",
        "deployment": "Yayına alma ve shadow test önerisi",
        "artifact_manifest": "Artefakt manifestosu",
        "section_note": "Yorum",
        "academic_conclusion": "Karşılaştırma istatistiksel olarak güçlü bir genel kazanan ortaya koymadı. Random Forest birkaç kayıtlı ölçütte öne çıktı, ancak küçük holdout ve tek öğretmen örneklemi üretim düzeyinde sonuca izin vermiyor.",
        "technical_conclusion": "Doğrulanmış inceleme, bu çalışmanın teknik kanıt paketi olarak kullanılabileceğini ancak dağıtım kararı olarak kullanılamayacağını gösteriyor.",
        "artifact_name": "Artefakt",
        "artifact_purpose": "Amaç",
        "artifact_format": "Biçim",
        "artifact_checksum": "Sağlama",
        "artifact_availability": "Kullanılabilirlik",
        "artifact_filename": "Saklanan dosya adı",
        "system": "Sistem",
        "current_approach": "Mevcut yaklaşım",
        "business_use": "İş kullanımı",
        "evidence": "Kanıt",
        "recommended_action": "Önerilen eylem",
        "priority": "Öncelik",
        "component": "Bileşen",
        "impact": "İş etkisi",
        "owner": "Sorumlu",
        "review_trigger": "İnceleme tetikleyicisi",
        "model": "Model",
        "result": "Sonuç",
        "interpretation": "Yorum",
        "caption_portfolio": "Yönetici panelindeki zekâ çalışma alanında tartışılan sistemleri özetleyen portföy tablosu.",
        "caption_actions": "Yönetici iş akışıyla hizalanmış öncelikli kararlar tablosu.",
        "caption_models": "Doğrulanmış çalışma artefaktlarındaki denetimli modellerin okunabilir karşılaştırması.",
        "caption_feature_health": "Saklanan denetim ve gözden geçirme çıktısından üretilen özellik sağlığı tablosu.",
        "caption_manifest": "Depo yollarını göstermeden teknik kanıt paketini özetleyen artefakt manifestosu.",
        "visual_qa_passed": "Görsel render incelemesi için hazırlandı",
    },
}


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _copy(lang: str, key: str, **kwargs) -> str:
    template = _COPY[_lang(lang)].get(key, _COPY["en"].get(key, key))
    return template.format(**kwargs)


def _now_text(lang: str) -> str:
    stamp = datetime.now().astimezone()
    if lang == "es":
        return stamp.strftime("%d/%m/%Y %H:%M")
    if lang == "tr":
        return stamp.strftime("%d.%m.%Y %H:%M")
    return stamp.strftime("%Y-%m-%d %H:%M")


def _lang(lang: str | None) -> str:
    safe = _clean_text(lang).lower()
    return safe if safe in {"en", "es", "tr"} else "en"


def _report_dir(run_id: str, lang: str) -> Path:
    return REPORT_ROOT / _clean_text(run_id) / _lang(lang)


def _report_filename(report_type: str, run_id: str) -> str:
    mapping = {
        "experiment_docx": f"classio_experiment_report_{run_id}_v{EXPERIMENT_REPORT_TEMPLATE_VERSION}.docx",
        "executive_docx": f"classio_eic_executive_report_{run_id}.docx",
        "academic_docx": f"classio_eic_academic_report_{run_id}.docx",
        "technical_docx": f"classio_eic_technical_report_{run_id}.docx",
    }
    return mapping[report_type]


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _artifact_path_map(run_id: str) -> dict[str, Path]:
    rows = list_run_artifacts(run_id)
    mapping = {
        str(row.get("artifact_type") or ""): Path(str(row.get("storage_path") or ""))
        for row in rows
        if str(row.get("artifact_type") or "").strip() and str(row.get("storage_path") or "").strip()
    }
    if "findings_interpretation_report_md" not in mapping and "academic_report_md" in mapping:
        mapping["findings_interpretation_report_md"] = mapping["academic_report_md"]
    return mapping


def _set_font(run, size: float, *, bold: bool = False, color: RGBColor | None = None, name: str = "Arial", italic: bool = False) -> None:
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:ascii"), name)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), name)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    if color:
        run.font.color.rgb = color


def _set_doc_defaults(doc: Document) -> None:
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.8)
        section.right_margin = Inches(0.8)
        section.header_distance = Inches(0.35)
        section.footer_distance = Inches(0.35)
    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
    normal.font.size = Pt(10.5)
    pf = normal.paragraph_format
    pf.space_after = Pt(7)
    pf.space_before = Pt(0)
    pf.line_spacing = 1.15
    style_map = {
        "Title": (22, CLASSIO_BLUE),
        "Subtitle": (11, MUTED),
        "Heading 1": (16, CLASSIO_BLUE),
        "Heading 2": (13, CLASSIO_BLUE),
        "Heading 3": (11.5, CLASSIO_TEAL),
    }
    for style_name, (size, color) in style_map.items():
        style = doc.styles[style_name]
        style.font.name = "Arial"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Arial")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Arial")
        style.font.size = Pt(size)
        style.font.color.rgb = color
        style.font.bold = True
        style.paragraph_format.space_after = Pt(6)


def _add_page_number(paragraph) -> None:
    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)


def _apply_page_furniture(doc: Document, report_name: str, run_id: str, lang: str) -> None:
    for section in doc.sections:
        header = section.header
        header.is_linked_to_previous = False
        hp = header.paragraphs[0]
        hp.text = ""
        hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        hr = hp.add_run(f"Classio · {report_name} · {run_id}")
        _set_font(hr, 8.5, color=MUTED)
        footer = section.footer
        footer.is_linked_to_previous = False
        fp = footer.paragraphs[0]
        fp.text = ""
        fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        fr = fp.add_run(_copy(lang, "confidential") + " · ")
        _set_font(fr, 8.2, color=MUTED)
        _add_page_number(fp)


def _cover(doc: Document, title: str, subtitle: str, status: str, meta_lines: list[str], lang: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(78)
    run = p.add_run(_copy(lang, "cover_kicker"))
    _set_font(run, 11.5, bold=True, color=CLASSIO_GOLD)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.paragraph_format.space_before = Pt(16)
    p2.paragraph_format.space_after = Pt(6)
    r2 = p2.add_run(title)
    _set_font(r2, 24, bold=True, color=CLASSIO_BLUE)

    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p3.paragraph_format.space_after = Pt(16)
    r3 = p3.add_run(subtitle)
    _set_font(r3, 11, color=MUTED)

    p4 = doc.add_paragraph()
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p4.paragraph_format.space_after = Pt(16)
    r4 = p4.add_run(_copy(lang, "cover_status", value=status))
    _set_font(r4, 10.5, bold=True, color=CLASSIO_TEAL)

    for line in meta_lines:
        meta = doc.add_paragraph()
        meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
        meta.paragraph_format.space_after = Pt(4)
        mr = meta.add_run(line)
        _set_font(mr, 10, color=MUTED)
    doc.add_page_break()


def _add_heading(doc: Document, text: str, level: int = 1) -> None:
    heading = doc.add_paragraph(style=f"Heading {level}")
    heading.paragraph_format.keep_with_next = True
    heading.paragraph_format.space_before = Pt(10 if level == 1 else 6)
    heading.paragraph_format.space_after = Pt(4)
    run = heading.add_run(text)
    _set_font(run, {1: 16, 2: 13, 3: 11.5}.get(level, 10.5), bold=True, color=CLASSIO_BLUE if level < 3 else CLASSIO_TEAL)


def _add_paragraph(doc: Document, text: str, *, italic: bool = False, color: RGBColor | None = None) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text)
    _set_font(run, 10.5, color=color or RGBColor(40, 40, 40), italic=italic)


def _add_bullets(doc: Document, rows: list[str]) -> None:
    for row in rows:
        if not _clean_text(row):
            continue
        para = doc.add_paragraph(style="List Bullet")
        para.paragraph_format.space_after = Pt(4)
        run = para.add_run(str(row))
        _set_font(run, 10.3, color=RGBColor(40, 40, 40))


def _unique_nonempty(rows: list[Any]) -> list[str]:
    seen: set[str] = set()
    values: list[str] = []
    for row in rows:
        text = _clean_text(row)
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return values


def _add_note_box(doc: Document, title: str, body: str) -> None:
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    _set_table_width(table, 6.7)
    cell = table.rows[0].cells[0]
    _set_cell_width(cell, 6.7)
    _shade_cell(cell, NOTE_FILL)
    _set_cell_margins(cell, top=110, bottom=110, left=140, right=140)
    p1 = cell.paragraphs[0]
    p1.paragraph_format.space_after = Pt(2)
    r1 = p1.add_run(title)
    _set_font(r1, 10.2, bold=True, color=CLASSIO_BLUE)
    p2 = cell.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    r2 = p2.add_run(body)
    _set_font(r2, 10, color=RGBColor(50, 50, 50))
    doc.add_paragraph("")


def _short_fingerprint(value: str) -> str:
    safe = _clean_text(value)
    return safe[:12] + "..." if len(safe) > 15 else safe


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _pct(value: Any) -> str:
    return f"{round(_float(value) * 100.0, 1)}%"


def _humanize_identifier(value: Any) -> str:
    safe = _clean_text(value)
    if not safe:
        return _copy("en", "not_available")
    tokens = safe.replace(".", " ").replace("_", " ").replace("-", " ").split()
    words: list[str] = []
    for token in tokens:
        lower = token.lower()
        if lower in {"id", "json", "csv", "md", "pdf", "docx", "roc", "auc", "f1"}:
            words.append(token.upper())
        elif lower.startswith("v") and lower[1:].isdigit():
            words.append(token.upper())
        elif token.isupper() and len(token) <= 5:
            words.append(token)
        else:
            words.append(token.capitalize())
    return " ".join(words)


def _display_scalar(value: Any) -> str:
    if value in (None, "", "None"):
        return "n/a"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, float):
        return str(round(value, 4))
    return _humanize_identifier(value) if isinstance(value, str) and ("_" in value or "." in value or "-" in value) else str(value)


def _display_jsonish(value: Any, *, max_chars: int = 160) -> str:
    payload = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return "{}"
        try:
            payload = json.loads(text)
        except Exception:
            return text[:max_chars]
    if isinstance(payload, dict):
        pieces = [f"{_humanize_identifier(key)}: {_display_scalar(item)}" for key, item in payload.items()]
        rendered = "; ".join(pieces) if pieces else "{}"
        return rendered[:max_chars]
    if isinstance(payload, list):
        rendered = ", ".join(_display_scalar(item) for item in payload)
        return rendered[:max_chars]
    return str(payload)[:max_chars]


def _humanize_list(values: list[Any]) -> str:
    return ", ".join(_humanize_identifier(value) for value in values if _clean_text(value))


def _artifact_display_name(artifact_type: str) -> str:
    mapping = {
        "academic_report_md": "Findings Interpretation Report Markdown",
        "findings_interpretation_report_md": "Findings Interpretation Report Markdown",
        "dataset_summary_json": "Dataset Summary JSON",
        "feature_audit_csv": "Feature Audit CSV",
        "frozen_dataset_csv": "Frozen Dataset CSV",
        "holdout_predictions_csv": "Holdout Predictions CSV",
        "integrity_review_md": "Integrity Review Markdown",
        "integrity_report_md": "Integrity Report Markdown",
        "label_audit_csv": "Label Audit CSV",
        "label_reconciliation_csv": "Label Reconciliation CSV",
        "model_comparison_csv": "Model Comparison CSV",
        "run_summary_json": "Run Summary JSON",
        "technical_report_md": "Technical Report Markdown",
    }
    return mapping.get(_clean_text(artifact_type), _humanize_identifier(artifact_type))


def _hash_file(path: Path) -> str:
    if not path.exists():
        return "missing"
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return digest[:10]


def _set_table_width(table, width_in: float) -> None:
    tbl_pr = table._tbl.tblPr
    tbl_layout = tbl_pr.find(qn("w:tblLayout"))
    if tbl_layout is None:
        tbl_layout = OxmlElement("w:tblLayout")
        tbl_pr.append(tbl_layout)
    tbl_layout.set(qn("w:type"), "fixed")
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:type"), "dxa")
    tbl_w.set(qn("w:w"), str(int(width_in * 1440)))


def _section_content_width(doc: Document) -> float:
    section = doc.sections[-1]
    usable = section.page_width - section.left_margin - section.right_margin
    return max(4.5, usable / 914400.0)


def _fit_table_widths(widths: list[float], max_width: float) -> list[float]:
    if not widths:
        return widths
    total = sum(widths)
    if total <= 0:
        return widths
    target = max(3.5, max_width - TABLE_WIDTH_GUTTER)
    if total <= target:
        return widths
    scale = target / total
    return [round(width * scale, 4) for width in widths]


def _set_cell_width(cell, width_in: float) -> None:
    cell.width = Inches(width_in)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:type"), "dxa")
    tc_w.set(qn("w:w"), str(int(width_in * 1440)))


def _set_cell_margins(cell, *, top: int = 80, bottom: int = 80, left: int = 120, right: int = 120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.find(qn("w:tcMar"))
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for key, value in {"top": top, "bottom": bottom, "left": left, "right": right}.items():
        node = tc_mar.find(qn(f"w:{key}"))
        if node is None:
            node = OxmlElement(f"w:{key}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def _shade_cell(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def _mark_header_row(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tag = tr_pr.find(qn("w:tblHeader"))
    if tag is None:
        tag = OxmlElement("w:tblHeader")
        tr_pr.append(tag)
    tag.set(qn("w:val"), "true")


def _prevent_row_split(row) -> None:
    tr_pr = row._tr.get_or_add_trPr()
    tag = tr_pr.find(qn("w:cantSplit"))
    if tag is None:
        tag = OxmlElement("w:cantSplit")
        tr_pr.append(tag)


def _configure_table(table, widths: list[float], *, header_fill: str = TABLE_HEADER_FILL) -> list[float]:
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    table.autofit = False
    _set_table_width(table, sum(widths))
    for row in table.rows:
        row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
        _prevent_row_split(row)
    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            width = widths[min(idx, len(widths) - 1)]
            _set_cell_width(cell, width)
            _set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            for para in cell.paragraphs:
                para.paragraph_format.space_after = Pt(2)
                para.paragraph_format.line_spacing = 1.05
    if table.rows:
        _mark_header_row(table.rows[0])
        for cell in table.rows[0].cells:
            _shade_cell(cell, header_fill)
    return widths


def _add_table(
    doc: Document,
    headers: list[str],
    rows: list[list[str]],
    widths: list[float],
    *,
    caption: str = "",
    numeric_cols: set[int] | None = None,
) -> None:
    numeric_cols = numeric_cols or set()
    fitted_widths = _fit_table_widths(widths, _section_content_width(doc))
    header_font_size = 9.6 if len(headers) <= 5 else 9.1
    body_font_size = 9.2 if len(headers) <= 5 else 8.8
    table = doc.add_table(rows=1, cols=len(headers))
    hdr = table.rows[0].cells
    for idx, header in enumerate(headers):
        p = hdr[idx].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(str(header))
        _set_font(r, header_font_size, bold=True, color=CLASSIO_BLUE)
    for row in rows:
        cells = table.add_row().cells
        for idx, value in enumerate(row):
            p = cells[idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.RIGHT if idx in numeric_cols else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(str(value))
            _set_font(r, body_font_size, color=RGBColor(45, 45, 45))
    _configure_table(table, fitted_widths)
    if caption:
        _add_caption(doc, caption)
    doc.add_paragraph("")


def _add_caption(doc: Document, caption: str) -> None:
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(1)
    para.paragraph_format.space_after = Pt(8)
    run = para.add_run(caption)
    _set_font(run, 8.8, italic=True, color=MUTED)


def _add_picture_with_caption(doc: Document, image_path: Path, caption: str, *, width: float = 6.5) -> None:
    if not image_path.exists():
        return
    doc.add_picture(str(image_path), width=Inches(width))
    _add_caption(doc, caption)


def _add_landscape_section(doc: Document) -> None:
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    section.top_margin = Inches(0.65)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.75)
    section.right_margin = Inches(0.75)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)


def _add_portrait_section(doc: Document) -> None:
    section = doc.add_section(WD_SECTION.NEW_PAGE)
    section.orientation = WD_ORIENT.PORTRAIT
    section.top_margin = Inches(0.8)
    section.bottom_margin = Inches(0.75)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)
    section.header_distance = Inches(0.35)
    section.footer_distance = Inches(0.35)


def _verified_docx_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    with ZipFile(BytesIO(data), "r") as handle:
        if "word/document.xml" not in handle.namelist():
            raise BadZipFile("Missing word/document.xml")
    return data


def _validated_run_detail(run_id: str) -> dict[str, Any]:
    detail = eic_service.get_experiment_business_detail(run_id, cache_bust=f"report-{run_id}")
    if not detail:
        return {}
    if _clean_text(detail.get("run_status")) not in FINAL_VALIDATED_RUN_STATES:
        return {}
    return detail


def _report_base_context(run_id: str, lang: str) -> dict[str, Any]:
    detail = _validated_run_detail(run_id)
    if not detail:
        return {}
    academic = eic_service.get_academic_evidence_summary(run_id, cache_bust=f"academic-{run_id}")
    telemetry = eic_service.get_business_telemetry_health(cache_bust=f"telemetry-{run_id}")
    portfolio = eic_service.get_intelligence_component_portfolio(cache_bust=f"portfolio-{run_id}")
    decisions = eic_service.get_prioritized_intelligence_decisions(cache_bust=f"decisions-{run_id}")
    latest_summary = eic_service.get_intelligence_business_summary(cache_bust=f"summary-{run_id}")
    artifacts = _artifact_path_map(run_id)
    run_summary = _read_json(artifacts.get("run_summary_json", Path("__missing__")))
    dataset_summary = _read_json(artifacts.get("dataset_summary_json", Path("__missing__")))
    return {
        "detail": detail,
        "academic": academic,
        "telemetry": telemetry,
        "portfolio": portfolio,
        "decisions": decisions,
        "latest_summary": latest_summary,
        "run_summary": run_summary,
        "dataset_summary": dataset_summary,
        "lang": lang,
    }


def _report_chart_assets(report_type: str, run_id: str, lang: str, context: dict[str, Any]) -> dict[str, Path]:
    assets_dir = _report_dir(run_id, lang) / f"assets_{report_type}"
    assets_dir.mkdir(parents=True, exist_ok=True)
    return build_report_charts(report_type, run_id, lang, context, _artifact_path_map(run_id), assets_dir)


def _available_or_message(required: bool, lang: str) -> dict[str, Any] | None:
    if required:
        return None
    return {"ok": False, "message": t("admin_eic_report_unavailable_no_validated_run", lang=lang)}


def _append_source_note(doc: Document, lang: str) -> None:
    para = doc.add_paragraph()
    para.paragraph_format.space_before = Pt(0)
    para.paragraph_format.space_after = Pt(10)
    run = para.add_run(_copy(lang, "source_note"))
    _set_font(run, 8.7, italic=True, color=MUTED)


def _bool_text(value: Any, lang: str) -> str:
    normalized = _clean_text(value).lower()
    return _copy(lang, "yes") if normalized in {"1", "true", "yes"} else _copy(lang, "no")


def _model_name(value: str, lang: str) -> str:
    return str(get_model_comparison_value_display("model_name", value, lang=lang))


def _narrative_robust_winner(detail: dict[str, Any], run_summary: dict[str, Any], lang: str) -> str:
    evaluation = run_summary.get("evaluation") or {}
    leader = _model_name(_clean_text(evaluation.get("primary_metric_leader") or detail.get("primary_metric_leader")), lang)
    if _clean_text(detail.get("run_status")) == "VALIDATED_EXPLORATORY_RUN":
        return f"{leader} led the validated comparison strongly enough to justify controlled shadow testing."
    return _copy(lang, "academic_conclusion")


def _required_artifacts_present(report_type: str, context: dict[str, Any], artifacts: dict[str, Path]) -> bool:
    if report_type == "executive_docx":
        return bool(context.get("detail") and context.get("portfolio") and context.get("decisions"))
    if report_type == "academic_docx":
        return bool(context.get("run_summary") and context.get("dataset_summary") and ((artifacts.get("model_comparison_csv") and artifacts["model_comparison_csv"].exists()) or (context.get("detail", {}).get("model_results") or {}).get("models_compared")))
    if report_type == "technical_docx":
        artifact_complete = all(
            artifacts.get(key) and artifacts[key].exists()
            for key in ["run_summary_json", "dataset_summary_json", "model_comparison_csv", "holdout_predictions_csv", "feature_audit_csv"]
        )
        context_complete = bool(
            context.get("run_summary")
            and context.get("dataset_summary")
            and ((context.get("detail", {}).get("model_results") or {}).get("models_compared"))
        )
        return artifact_complete or context_complete
    return False


def _metadata_rows(detail: dict[str, Any], run_summary: dict[str, Any], dataset_summary: dict[str, Any], lang: str) -> list[list[str]]:
    dataset = run_summary.get("dataset") or dataset_summary
    evaluation = run_summary.get("evaluation") or {}
    return [
        [_copy(lang, "meta_field"), _copy(lang, "meta_value")],
        [t("admin_eic_run_status", lang=lang), get_run_status_display(str(detail.get("run_status") or ""), lang=lang)],
        [t("admin_eic_integrity_status", lang=lang), get_integrity_status_display(str(detail.get("integrity_status") or ""), lang=lang)],
        [t("admin_eic_registry_maturity", lang=lang), get_maturity_display(str(detail.get("maturity_verdict") or ""), lang=lang)],
        [t("admin_eic_report_target_version", lang=lang), _humanize_identifier(dataset_summary.get("target_version") or "opened_within_7d_v1")],
        [t("admin_eic_report_feature_schema", lang=lang), _humanize_identifier(dataset_summary.get("feature_schema_version") or dataset.get("feature_schema_version") or "n/a")],
        [t("admin_eic_report_run_id", lang=lang, value="").split(":")[0], str(detail.get("run_id") or "")],
        [t("admin_eic_report_dataset_fingerprint", lang=lang, value="").split(":")[0], str(detail.get("dataset_fingerprint") or "")],
        ["Chronological cutoff", str(detail.get("chronological_cutoff") or evaluation.get("cutoff_timestamp") or "n/a")],
    ]


def _dataset_accounting_rows(detail: dict[str, Any], run_summary: dict[str, Any], dataset_summary: dict[str, Any]) -> list[list[str]]:
    dataset = run_summary.get("dataset") or dataset_summary
    evaluation = run_summary.get("evaluation") or {}
    rows = [
        ["Source rows", str(dataset.get("source_row_count") or "n/a")],
        ["Included rows", str(dataset.get("included_row_count") or detail.get("included_row_count") or "n/a")],
        ["Positives", str(dataset.get("positive_count") or detail.get("positive_label_count") or "n/a")],
        ["Negatives", str(dataset.get("negative_count") or detail.get("negative_label_count") or "n/a")],
        ["Right-censored", str(dataset.get("excluded_row_count") or "0")],
        ["Teachers represented", str(dataset.get("teacher_count") or detail.get("teachers_represented") or "0")],
        ["Students represented", str(dataset.get("student_count") or detail.get("students_represented") or "0")],
        ["Resources represented", str(dataset.get("resource_count") or detail.get("resources_represented") or "0")],
        ["Date range", f"{(dataset.get('date_range') or {}).get('assigned_at_min') or detail.get('source_start_at') or 'n/a'} to {(dataset.get('date_range') or {}).get('assigned_at_max') or detail.get('source_end_at') or 'n/a'}"],
        ["Chronological cutoff", str(evaluation.get("cutoff_timestamp") or detail.get("chronological_cutoff") or "n/a")],
        ["Development rows", str(evaluation.get("development_count") or "n/a")],
        ["Holdout rows", str(evaluation.get("holdout_count") or "n/a")],
    ]
    for reason, count in (dataset.get("exclusion_reasons") or {}).items():
        if reason == "included":
            continue
        rows.append([f"Excluded: {_humanize_identifier(reason)}", str(count)])
    return rows


def _portfolio_rows(portfolio: list[dict[str, Any]], lang: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in portfolio:
        rows.append(
            [
                get_component_display_name(str(row.get("component_id") or ""), lang=lang),
                get_component_type_display(str(row.get("component_type") or ""), lang=lang),
                str(row.get("production_use") or row.get("decision_supported") or ""),
                get_evidence_display(str(row.get("evidence_maturity") or row.get("validated_evidence_status") or ""), lang=lang),
                get_business_action_display(str(row.get("recommended_next_action") or ""), lang=lang),
            ]
        )
    return rows


def _decision_rows(decisions: list[dict[str, Any]], lang: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in decisions:
        issue = str(row.get("issue") or "")
        evidence = str(row.get("evidence") or "")
        impact = str(row.get("business_impact") or "")
        rows.append(
            [
                str(row.get("urgency") or "").title() or _copy(lang, "not_available"),
                get_component_display_name(str(row.get("component_id") or ""), lang=lang),
                evidence,
                impact,
                get_business_action_display(str(row.get("recommended_action") or ""), lang=lang),
                str(row.get("responsible_area") or ""),
                issue,
            ]
        )
    return rows


def _feature_health_rows(run_summary: dict[str, Any], lang: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in (run_summary.get("review") or {}).get("feature_health") or []:
        rows.append(
            [
                _humanize_identifier(row.get("feature") or ""),
                "Stored review",
                "Past-only",
                f"{round(_float(row.get('overall_missing_percentage')), 2)}%",
                f"{round(_float(row.get('development_missing_percentage')), 2)}%",
                f"{round(_float(row.get('holdout_missing_percentage')), 2)}%",
                _bool_text(not row.get("excluded_from_logistic_regression_reduced"), lang),
                str(row.get("missingness_explanation") or ""),
            ]
        )
    return rows


def _model_metric_groups(model_rows: list[dict[str, Any]], lang: str) -> list[tuple[str, list[str], list[list[str]], list[float], set[int]]]:
    group_specs = [
        (
            "Discrimination and ranking",
            ["model_name", "roc_auc", "average_precision", "balanced_accuracy", "f1", "delta_vs_dummy_roc_auc"],
            [1, 2, 3, 4, 5],
            [2.2, 1.2, 1.2, 1.2, 1.0, 1.5],
        ),
        (
            "Calibration and thresholding",
            ["model_name", "log_loss", "brier_score", "predicted_positive_rate", "best_f1", "best_balanced_accuracy"],
            [1, 2, 3, 4, 5],
            [2.1, 1.2, 1.2, 1.4, 1.0, 1.5],
        ),
        (
            "Runtime and status",
            ["model_name", "status", "cv_primary_metric_mean", "cv_primary_metric_variance", "train_duration_seconds", "inference_duration_seconds"],
            [2, 3, 4, 5],
            [2.1, 1.2, 1.5, 1.5, 1.5, 1.6],
        ),
    ]
    groups = []
    for title, columns, numeric_cols, widths in group_specs:
        headers = [get_model_comparison_column_display(column, lang=lang) for column in columns]
        rows: list[list[str]] = []
        for row in model_rows:
            rendered = [str(get_model_comparison_value_display(column, row.get(column), lang=lang) or "—") for column in columns]
            rows.append(rendered)
        groups.append((title, headers, rows, widths, set(numeric_cols)))
    return groups


def _artifact_manifest_rows(artifacts: dict[str, Path], lang: str) -> tuple[list[list[str]], list[str]]:
    purpose_map = {
        "run_summary_json": "Validated run summary",
        "dataset_summary_json": "Dataset accounting and counts",
        "model_comparison_csv": "Stored model metrics",
        "holdout_predictions_csv": "Stored holdout probabilities",
        "feature_audit_csv": "Feature availability audit",
        "label_reconciliation_csv": "Label reconciliation review",
        "integrity_report_md": "Integrity narrative",
        "academic_report_md": "Findings interpretation markdown baseline",
        "findings_interpretation_report_md": "Findings interpretation markdown baseline",
        "technical_report_md": "Technical markdown baseline",
    }
    rows: list[list[str]] = []
    filenames: list[str] = []
    for artifact_type, path in sorted(artifacts.items()):
        filenames.append(path.name)
        rows.append(
            [
                _artifact_display_name(artifact_type),
                purpose_map.get(artifact_type, "Stored supporting artifact"),
                path.suffix.lstrip(".") or "file",
                _hash_file(path),
                _copy(lang, "yes") if path.exists() else _copy(lang, "no"),
            ]
        )
    return rows, filenames


def build_executive_report_docx(run_id: str, language: str) -> dict[str, Any]:
    lang = _lang(language)
    context = _report_base_context(run_id, lang)
    if not context:
        return {"ok": False, "message": t("admin_eic_report_unavailable_no_validated_run", lang=lang)}
    artifacts = _artifact_path_map(run_id)
    if not _required_artifacts_present("executive_docx", context, artifacts):
        return {"ok": False, "message": t("admin_eic_report_unavailable_no_validated_run", lang=lang)}
    detail = context["detail"]
    summary = context["latest_summary"]
    telemetry = context["telemetry"]
    portfolio = context["portfolio"]
    decisions = context["decisions"]
    run_summary = context["run_summary"]
    dataset = run_summary.get("dataset") or context["dataset_summary"]
    charts = _report_chart_assets("executive_docx", run_id, lang, context)

    doc = Document()
    _set_doc_defaults(doc)
    _cover(
        doc,
        _copy(lang, "executive_report_name"),
        t("admin_eic_report_exec_subtitle", lang=lang),
        get_run_status_display(str(detail.get("run_status") or ""), lang=lang),
        [
            _copy(lang, "cover_generated", value=_now_text(lang)),
            _copy(lang, "cover_run", value=run_id),
            _copy(lang, "cover_fingerprint", value=_short_fingerprint(str(detail.get("dataset_fingerprint") or "n/a"))),
        ],
        lang,
    )
    _apply_page_furniture(doc, _copy(lang, "executive_report_name"), run_id, lang)

    _add_heading(doc, t("admin_eic_report_exec_summary_heading", lang=lang), 1)
    _add_paragraph(doc, _copy(lang, "exec_intro"))
    top_decision = summary.get("top_decision") or {}
    summary_rows = [
        [_copy(lang, "what_was_evaluated"), str(detail.get("business_question") or "")],
        [_copy(lang, "what_evidence_showed"), _narrative_robust_winner(detail, run_summary, lang)],
        [_copy(lang, "replacement_question"), _copy(lang, "exec_replace_hold")],
        [_copy(lang, "leadership_action"), get_business_action_display(str(top_decision.get("recommended_action") or detail.get("recommended_business_action") or ""), lang=lang)],
        [_copy(lang, "missing_evidence"), _copy(lang, "exec_missing")],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], summary_rows, [2.1, 4.6], caption=_copy(lang, "summary_snapshot"))

    _add_heading(doc, _copy(lang, "exec_findings"), 1)
    kpi_rows = [
        ["Mature labelled observations", str(dataset.get("included_row_count") or detail.get("included_row_count") or 0)],
        ["Teachers represented", str(detail.get("teachers_represented") or 0)],
        ["Students represented", str(detail.get("students_represented") or 0)],
        ["Resources represented", str(detail.get("resources_represented") or 0)],
        ["Validation status", get_run_status_display(str(detail.get("run_status") or ""), lang=lang)],
        ["Evidence strength", get_evidence_display(str(detail.get("evidence_level") or detail.get("evidence_verdict") or ""), lang=lang)],
        ["Robust winner", _bool_text(detail.get("robust_winner"), lang)],
        ["Current recommendation", get_business_action_display(str(detail.get("recommended_business_action") or top_decision.get("recommended_action") or ""), lang=lang)],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], kpi_rows, [2.8, 3.9])

    _add_picture_with_caption(doc, charts.get("component_maturity", Path("__missing__")), "Figure 1. Intelligence component maturity distribution.", width=6.3)
    _add_picture_with_caption(doc, charts.get("label_balance", Path("__missing__")), "Figure 2. Label balance for the validated supervised run.", width=5.7)
    _add_picture_with_caption(doc, charts.get("telemetry_surface", Path("__missing__")), "Figure 3. Matched-open coverage by telemetry surface in the recent admin telemetry window.", width=6.4)
    _add_picture_with_caption(doc, charts.get("decision_urgency", Path("__missing__")), "Figure 4. Prioritized decisions by urgency.", width=5.8)
    _append_source_note(doc, lang)

    _add_heading(doc, _copy(lang, "portfolio_summary"), 1)
    _add_table(
        doc,
        [_copy(lang, "system"), _copy(lang, "current_approach"), _copy(lang, "business_use"), _copy(lang, "evidence"), _copy(lang, "recommended_action")],
        _portfolio_rows(portfolio, lang),
        [1.6, 1.2, 2.2, 0.9, 1.0],
        caption=_copy(lang, "caption_portfolio"),
    )

    _add_heading(doc, _copy(lang, "data_feedback_health"), 1)
    telemetry_summary = telemetry.get("summary") or {}
    zero_note = (
        "Zero recent canonical exposures were recorded in the selected telemetry window; matched-open coverage cannot yet be interpreted as model failure."
        if _int(telemetry_summary.get("total_canonical_exposures")) == 0
        else ""
    )
    _add_bullets(
        doc,
        [
            t("admin_eic_report_data_health_line_exposures", lang=lang, value=str(telemetry_summary.get("total_canonical_exposures") or 0)),
            t("admin_eic_report_data_health_line_match", lang=lang, value=_pct(telemetry_summary.get("matched_open_coverage") or 0.0)),
            t("admin_eic_report_data_health_line_unmatched", lang=lang, value=str(telemetry_summary.get("unmatched_opens") or 0)),
            t("admin_eic_report_data_health_line_freshness", lang=lang, value=str(telemetry_summary.get("telemetry_freshness_hours") or "n/a")),
            zero_note,
        ],
    )

    _add_heading(doc, _copy(lang, "business_risks"), 1)
    _add_bullets(doc, list(detail.get("limitations") or [t("admin_eic_report_no_additional_risks", lang=lang)]))

    _add_heading(doc, _copy(lang, "prioritized_actions"), 1)
    _add_table(
        doc,
        [_copy(lang, "priority"), _copy(lang, "component"), _copy(lang, "evidence"), _copy(lang, "impact"), _copy(lang, "recommended_action"), _copy(lang, "owner"), _copy(lang, "review_trigger")],
        _decision_rows(decisions, lang),
        [0.7, 1.3, 2.0, 1.6, 1.1, 0.9, 1.3],
        caption=_copy(lang, "caption_actions"),
    )

    _add_heading(doc, _copy(lang, "roadmap"), 1)
    _add_note_box(
        doc,
        "Next review milestone",
        "Review again after broader teacher coverage is available or when repeated validated runs show stable evidence with cleaner telemetry matching.",
    )

    _add_heading(doc, _copy(lang, "run_metadata"), 1)
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], _metadata_rows(detail, run_summary, context["dataset_summary"], lang)[1:], [2.2, 4.5])

    report_dir = _report_dir(run_id, lang)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / _report_filename("executive_docx", run_id)
    doc.save(path)
    return {"ok": True, "path": str(path), "bytes": _verified_docx_bytes(path), "report_type": "executive_docx"}


def build_academic_report_docx(run_id: str, language: str) -> dict[str, Any]:
    lang = _lang(language)
    context = _report_base_context(run_id, lang)
    if not context:
        return {"ok": False, "message": t("admin_eic_report_unavailable_no_validated_run", lang=lang)}
    artifacts = _artifact_path_map(run_id)
    if not _required_artifacts_present("academic_docx", context, artifacts):
        return {"ok": False, "message": t("admin_eic_report_unavailable_no_validated_run", lang=lang)}
    detail = context["detail"]
    academic = context["academic"]
    run_summary = context["run_summary"]
    dataset_summary = context["dataset_summary"]
    evaluation = run_summary.get("evaluation") or {}
    charts = _report_chart_assets("academic_docx", run_id, lang, context)
    model_rows = list((detail.get("model_results") or {}).get("models_compared") or [])

    doc = Document()
    _set_doc_defaults(doc)
    _cover(
        doc,
        _copy(lang, "academic_report_name"),
        t("admin_eic_report_academic_subtitle", lang=lang),
        get_run_status_display(str(detail.get("run_status") or ""), lang=lang),
        [
            _copy(lang, "cover_generated", value=_now_text(lang)),
            _copy(lang, "cover_run", value=run_id),
            _copy(lang, "cover_fingerprint", value=_short_fingerprint(str(detail.get("dataset_fingerprint") or "n/a"))),
        ],
        lang,
    )
    _apply_page_furniture(doc, _copy(lang, "academic_report_name"), run_id, lang)

    _add_heading(doc, _copy(lang, "academic_abstract"), 1)
    _add_paragraph(doc, _copy(lang, "academic_conclusion"))

    academic_sections = [
        (_copy(lang, "company_context"), str(academic.get("company_context") or "")),
        (_copy(lang, "problem_statement"), "Classio operates live teaching, student-practice, and recommendation workflows with a growing need for internally validated learning evidence. The analytical question in this report is whether historical assignment context and pre-assignment signals can predict opening within seven days, and whether that signal is strong enough to support future product experimentation."),
        (_copy(lang, "solution_statement"), "This document summarizes a supervised binary-classification study designed for Classio's internal academic and research stakeholders. The target is the seven-day assignment-open label, and the analysis is framed as an evidence-building exercise for the company's reporting system rather than as a production-replacement decision on its own."),
        (_copy(lang, "smart_objective"), "Assess whether historical assignment and pre-assignment features can predict opening within seven days, compare multiple supervised algorithms under a chronological holdout, and determine whether any candidate demonstrates enough evidence to justify continued shadow testing and deeper internal review."),
        (_copy(lang, "supervised_formulation"), str(academic.get("target_definition") or "")),
    ]
    for heading, body in academic_sections:
        _add_heading(doc, heading, 1)
        _add_paragraph(doc, body)

    _add_heading(doc, _copy(lang, "dataset_sources"), 1)
    dataset_rows = [
        ["Dataset fingerprint", str(academic.get("dataset_fingerprint") or "")],
        ["Dataset size", str(academic.get("dataset_size") or 0)],
        ["Positive class balance", _pct(academic.get("class_balance") or 0.0)],
        ["Date coverage", f"{(academic.get('date_range') or {}).get('start') or 'n/a'} to {(academic.get('date_range') or {}).get('end') or 'n/a'}"],
        ["Data sources", ", ".join(academic.get("data_sources") or [])],
        ["Unit of analysis", str(academic.get("unit_of_analysis") or "")],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], dataset_rows, [2.0, 4.7])
    _add_picture_with_caption(doc, charts.get("label_balance", Path("__missing__")), "Figure 1. Stored class distribution for the validated run.", width=5.6)
    _add_picture_with_caption(doc, charts.get("split_timeline", Path("__missing__")), "Figure 2. Event timeline with the stored chronological cutoff.", width=6.4)

    _add_heading(doc, _copy(lang, "data_preparation"), 1)
    _add_bullets(
        doc,
        [
            "Inclusion and exclusion rules are taken from the stored dataset summary and the run review.",
            f"Included rows: {dataset_summary.get('included_row_count') or detail.get('included_row_count') or 0}.",
            f"Excluded rows: {dataset_summary.get('excluded_row_count') or 0}, primarily due to open observation windows.",
            "Right censoring is handled by excluding records whose seven-day observation window had not closed at extraction time.",
            "Feature engineering is restricted to information available at or before assignment time to avoid leakage.",
        ],
    )

    _add_heading(doc, _copy(lang, "feature_selection"), 1)
    feature_health = _feature_health_rows(run_summary, lang)
    if feature_health:
        _add_table(
            doc,
            ["Feature", "Source", "Prediction-time availability", "Overall missing", "Dev missing", "Holdout missing", "Included", "Explanation"],
            feature_health,
            [0.75, 0.75, 0.9, 0.65, 0.65, 0.75, 0.5, 1.75],
            caption=_copy(lang, "caption_feature_health"),
        )

    _add_heading(doc, _copy(lang, "target_construction"), 1)
    _add_paragraph(doc, "The target is opened_within_7d, derived from teacher_assignments.assigned_at and subsequent opened_at or viewed_at events inside a seven-day window. Negative cases are records whose observation window closed without a qualifying open event.")

    _add_heading(doc, _copy(lang, "methodology"), 1)
    methodology_rows = [
        ["Chronological cutoff", str((academic.get("train_holdout_split") or {}).get("chronological_cutoff") or evaluation.get("cutoff_timestamp") or "n/a")],
        ["Evaluation design", str(academic.get("evaluation_design") or "")],
        ["Baseline comparator", str(academic.get("baseline") or "DummyClassifier")],
        ["Primary metric leader", _model_name(str(academic.get("selected_metric_leader") or detail.get("primary_metric_leader") or ""), lang)],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], methodology_rows, [2.0, 4.7])

    _add_heading(doc, _copy(lang, "models_evaluated"), 1)
    model_summary_rows = [
        [
            str(row.get("model_name") or ""),
            str(get_model_comparison_value_display("model_kind", row.get("model_kind"), lang=lang) or ""),
            str(get_model_comparison_value_display("status", row.get("status"), lang=lang) or ""),
            str(row.get("overall_interpretation") or "Stored comparison available."),
        ]
        for row in model_rows
    ]
    _add_table(doc, [_copy(lang, "model"), "Kind", "Status", _copy(lang, "interpretation")], model_summary_rows, [1.5, 0.8, 0.8, 2.8], caption=_copy(lang, "caption_models"))

    _add_heading(doc, _copy(lang, "evaluation_metrics"), 1)
    _add_bullets(
        doc,
        [
            "Primary ranking metrics: ROC AUC and average precision.",
            "Decision metrics: balanced accuracy, precision, recall, specificity, and F1-score.",
            "Calibration diagnostics: Brier score and log loss.",
            "Confidence intervals are taken from the stored model comparison artifact when available.",
        ],
    )

    _add_heading(doc, _copy(lang, "results"), 1)
    _add_picture_with_caption(doc, charts.get("model_metrics", Path("__missing__")), "Figure 3. Stored model comparison snapshot using ROC AUC for readability.", width=6.5)
    _add_picture_with_caption(doc, charts.get("roc_curves", Path("__missing__")), "Figure 4. ROC curves from stored holdout predictions.", width=6.2)
    _add_picture_with_caption(doc, charts.get("pr_curves", Path("__missing__")), "Figure 5. Precision-recall curves from stored holdout predictions.", width=6.2)
    _add_picture_with_caption(doc, charts.get("leader_confusion", Path("__missing__")), "Figure 6. Confusion matrix for the primary ROC leader.", width=3.8)
    _add_picture_with_caption(doc, charts.get("calibration_curves", Path("__missing__")), "Figure 7. Calibration curves from stored holdout probabilities.", width=6.2)
    _append_source_note(doc, lang)

    _add_heading(doc, _copy(lang, "comparative_analysis"), 1)
    _add_paragraph(doc, _narrative_robust_winner(detail, run_summary, lang))
    _add_bullets(
        doc,
        [
            f"Primary ROC AUC leader: {_model_name(str(evaluation.get('primary_metric_leader') or detail.get('primary_metric_leader') or ''), lang)}.",
            f"Best thresholded classifier: {_model_name(str(evaluation.get('best_thresholded_classifier') or ''), lang)}.",
            f"Best precision-recall ranking: {_model_name(str(evaluation.get('best_precision_recall_ranking') or ''), lang)}.",
            f"Calibration leader: {_model_name(str(evaluation.get('calibration_leader') or ''), lang)}.",
        ],
    )

    _add_heading(doc, _copy(lang, "conclusions"), 1)
    _add_note_box(doc, _copy(lang, "section_note"), _copy(lang, "academic_conclusion"))

    _add_heading(doc, _copy(lang, "implementation"), 1)
    _add_paragraph(doc, "The present evidence supports continued offline evaluation, telemetry improvement, and internal academic review rather than immediate live replacement of the existing heuristic workflow.")

    _add_heading(doc, _copy(lang, "limitations"), 1)
    _add_bullets(doc, list(academic.get("limitations") or detail.get("limitations") or []))

    _add_heading(doc, _copy(lang, "future_work"), 1)
    _add_bullets(doc, list(academic.get("future_improvements") or []))

    _add_heading(doc, _copy(lang, "references"), 1)
    _add_bullets(
        doc,
        [
            "docs/classio_ml_blueprint.md",
            "reports/ml_architecture/assigned_resource_open_7d/.../assigned_resource_open_7d_run_summary.json",
            "reports/ml_architecture/assigned_resource_open_7d/.../assigned_resource_open_7d_integrity_review.md",
            "reports/ml_architecture/assigned_resource_open_7d/.../assigned_resource_open_7d_model_comparison.csv",
        ],
    )

    _add_heading(doc, _copy(lang, "appendix"), 1)
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], _dataset_accounting_rows(detail, run_summary, dataset_summary), [2.2, 4.5])

    report_dir = _report_dir(run_id, lang)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / _report_filename("academic_docx", run_id)
    doc.save(path)
    return {"ok": True, "path": str(path), "bytes": _verified_docx_bytes(path), "report_type": "academic_docx"}


def build_technical_report_docx(run_id: str, language: str) -> dict[str, Any]:
    lang = _lang(language)
    context = _report_base_context(run_id, lang)
    if not context:
        return {"ok": False, "message": t("admin_eic_report_unavailable_no_validated_run", lang=lang)}
    artifacts = _artifact_path_map(run_id)
    if not _required_artifacts_present("technical_docx", context, artifacts):
        return {"ok": False, "message": t("admin_eic_report_unavailable_no_validated_run", lang=lang)}
    detail = context["detail"]
    academic = context["academic"]
    run_summary = context["run_summary"]
    dataset_summary = context["dataset_summary"]
    evaluation = run_summary.get("evaluation") or {}
    review = run_summary.get("review") or {}
    charts = _report_chart_assets("technical_docx", run_id, lang, context)
    model_rows = list((detail.get("model_results") or {}).get("models_compared") or [])
    manifest_rows, filenames = _artifact_manifest_rows(artifacts, lang)

    doc = Document()
    _set_doc_defaults(doc)
    _cover(
        doc,
        _copy(lang, "technical_report_name"),
        t("admin_eic_report_technical_subtitle", lang=lang),
        get_run_status_display(str(detail.get("run_status") or ""), lang=lang),
        [
            _copy(lang, "cover_generated", value=_now_text(lang)),
            _copy(lang, "cover_run", value=run_id),
            _copy(lang, "cover_fingerprint", value=_short_fingerprint(str(detail.get("dataset_fingerprint") or "n/a"))),
        ],
        lang,
    )
    _apply_page_furniture(doc, _copy(lang, "technical_report_name"), run_id, lang)

    _add_heading(doc, _copy(lang, "technical_metadata"), 1)
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], _metadata_rows(detail, run_summary, dataset_summary, lang)[1:], [2.2, 4.5])

    _add_heading(doc, _copy(lang, "experiment_definition"), 1)
    _add_paragraph(doc, str(detail.get("business_question") or ""))
    _add_paragraph(doc, "Prediction target: opened_within_7d, based on assignment-open behavior within a seven-day window.")

    _add_heading(doc, _copy(lang, "source_logic"), 1)
    _add_bullets(
        doc,
        [
            "Source tables: teacher_assignments, teacher_assignment_attempts, practice_sessions, resource_exposures, and resource_exposure_events.",
            "Extraction logic is frozen in the validated run artifacts and summarized in the dataset summary JSON.",
            "All feature construction is constrained to information known at or before assignment time.",
        ],
    )

    _add_heading(doc, _copy(lang, "dataset_accounting"), 1)
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], _dataset_accounting_rows(detail, run_summary, dataset_summary), [2.1, 4.6])
    _add_picture_with_caption(doc, charts.get("label_balance", Path("__missing__")), "Figure 1. Stored target/class distribution.", width=5.6)
    _add_picture_with_caption(doc, charts.get("split_timeline", Path("__missing__")), "Figure 2. Assignment timeline and chronological split cutoff.", width=6.4)

    _add_heading(doc, _copy(lang, "label_reconciliation"), 1)
    reconciliation = (review.get("label_reconciliation") or {})
    recon_rows = [
        ["Final verdict", get_run_status_display(str(review.get("final_verdict") or detail.get("run_status") or ""), lang=lang)],
        ["Exact row-level reconciliation", _bool_text(reconciliation.get("exact_row_level_reconciliation_available"), lang)],
        ["Legacy audit reconciliation applicable", _bool_text(reconciliation.get("legacy_audit_reconciliation_applicable"), lang)],
        ["Audit counts", json.dumps(reconciliation.get("audit_documented_counts") or {}, ensure_ascii=True)],
        ["Phase 3 counts", json.dumps(reconciliation.get("phase3_counts") or {}, ensure_ascii=True)],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], recon_rows, [2.4, 4.3])
    _add_bullets(doc, [str(reconciliation.get("likely_difference_explanation") or ""), str(detail.get("validation_notes") or "")])

    _add_heading(doc, _copy(lang, "leakage_controls"), 1)
    _add_bullets(
        doc,
        [
            "Chronological holdout keeps future assignments out of development data.",
            "Feature timestamps are checked against assignment time to enforce past-only availability.",
            "Feature missingness explanations in the stored review confirm that sparsity comes from history availability rather than identifier mismatch.",
        ],
    )

    _add_heading(doc, _copy(lang, "feature_health"), 1)
    _add_picture_with_caption(doc, charts.get("feature_missingness", Path("__missing__")), "Figure 3. Highest overall missingness rates from the stored feature audit.", width=6.4)
    feature_health_rows = _feature_health_rows(run_summary, lang)
    if feature_health_rows:
        _add_table(
            doc,
            ["Feature", "Source", "Availability", "Overall missing", "Dev missing", "Holdout missing", "Included", "Explanation"],
            feature_health_rows,
            [0.75, 0.75, 0.85, 0.65, 0.65, 0.75, 0.5, 2.2],
            caption=_copy(lang, "caption_feature_health"),
        )

    _add_heading(doc, _copy(lang, "preprocessing"), 1)
    _add_bullets(
        doc,
        [
            "Missing values are imputed only when the stored evaluation pipeline marked the feature as retained.",
            "Categorical features are encoded within the stored pipeline configuration; no report-time transformation modifies model outcomes.",
            "Fully missing development-slice features are automatically excluded before fitting, as documented in the integrity review.",
        ],
    )

    _add_heading(doc, _copy(lang, "cv_section"), 1)
    _add_bullets(
        doc,
        [
            f"Development rows: {evaluation.get('development_count') or 'n/a'} with {evaluation.get('development_positive_count') or 'n/a'} positives.",
            f"Holdout rows: {evaluation.get('holdout_count') or 'n/a'} with {evaluation.get('holdout_positive_count') or 'n/a'} positives.",
            "Cross-validation fold counts and mean metrics are read directly from the stored model comparison artifact.",
        ],
    )

    _add_heading(doc, _copy(lang, "model_configuration"), 1)
    config_rows = [
        [
            _model_name(str(row.get("model_name") or ""), lang),
            get_model_result_status_display(str(row.get("status") or ""), lang=lang),
            _display_jsonish(row.get("parameters_json") or {}, max_chars=200),
        ]
        for row in model_rows
    ]
    _add_table(doc, [_copy(lang, "model"), "Status", "Selected hyperparameters"], config_rows, [1.8, 0.9, 4.0])

    _add_heading(doc, _copy(lang, "baseline_results"), 1)
    _add_picture_with_caption(doc, charts.get("model_metrics", Path("__missing__")), "Figure 4. Model metric comparison snapshot using stored ROC AUC values.", width=6.6)
    _add_picture_with_caption(doc, charts.get("runtime", Path("__missing__")), "Figure 5. Training-runtime comparison from stored model outputs.", width=6.6)

    _add_heading(doc, _copy(lang, "threshold_analysis"), 1)
    threshold_rows = [
        ["Primary ROC leader", _model_name(str(evaluation.get("primary_metric_leader") or detail.get("primary_metric_leader") or ""), lang)],
        ["Best thresholded classifier", _model_name(str(evaluation.get("best_thresholded_classifier") or ""), lang)],
        ["Calibration leader", _model_name(str(evaluation.get("calibration_leader") or ""), lang)],
        ["Best precision-recall ranking", _model_name(str(evaluation.get("best_precision_recall_ranking") or ""), lang)],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], threshold_rows, [2.4, 4.3])

    confusion_targets = [
        ("baseline_confusion", "Figure 6. Confusion matrix for the stored baseline.", _clean_text("DummyClassifier")),
        ("leader_confusion", "Figure 7. Confusion matrix for the primary ROC leader.", _clean_text(evaluation.get("primary_metric_leader") or detail.get("primary_metric_leader") or "")),
        ("threshold_confusion", "Figure 8. Confusion matrix for the best thresholded classifier.", _clean_text(evaluation.get("best_thresholded_classifier") or "")),
    ]
    seen_confusion_models: set[str] = set()
    for chart_key, caption, model_name in confusion_targets:
        if not model_name or model_name in seen_confusion_models:
            continue
        seen_confusion_models.add(model_name)
        _add_picture_with_caption(doc, charts.get(chart_key, Path("__missing__")), caption, width=3.7)

    _add_heading(doc, _copy(lang, "roc_analysis"), 1)
    _add_picture_with_caption(doc, charts.get("roc_curves", Path("__missing__")), "Figure 9. ROC curves for score-capable stored models.", width=6.4)
    _add_paragraph(doc, _narrative_robust_winner(detail, run_summary, lang))

    _add_heading(doc, _copy(lang, "pr_analysis"), 1)
    _add_picture_with_caption(doc, charts.get("pr_curves", Path("__missing__")), "Figure 10. Precision-recall curves for the same stored holdout predictions.", width=6.4)

    _add_heading(doc, _copy(lang, "calibration_analysis"), 1)
    _add_picture_with_caption(doc, charts.get("calibration_curves", Path("__missing__")), "Figure 11. Calibration curves derived from stored probabilities.", width=6.4)
    _add_picture_with_caption(doc, charts.get("probability_distribution", Path("__missing__")), "Figure 12. Predicted-probability distributions for the stored leader, threshold leader, and baseline.", width=6.4)

    _add_heading(doc, _copy(lang, "error_analysis"), 1)
    _add_bullets(
        doc,
        [
            "False positives and false negatives can be inspected only through the stored anonymized holdout predictions; no raw user identifiers are exposed.",
            "Subgroup sample sizes are too small for strong technical claims by topic, student-history bucket, or resource type, so subgroup interpretation should remain descriptive only.",
            "The confusion matrices show that threshold choice changes the balance between misses and false alarms more than it changes the overall conclusion.",
        ],
    )

    _add_heading(doc, _copy(lang, "uncertainty"), 1)
    _add_bullets(
        doc,
        [
            "Confidence intervals are read from the stored model comparison CSV.",
            "Small holdout size and single-teacher coverage mean all uncertainty intervals should be interpreted conservatively.",
            f"Stored overall verdict: {get_run_status_display(str(review.get('final_verdict') or detail.get('run_status') or ''), lang=lang)}.",
        ],
    )

    _add_heading(doc, _copy(lang, "runtime"), 1)
    _add_paragraph(doc, "Training and inference durations are reported directly from the validated model comparison artifact and shown in Figure 5.")

    _add_heading(doc, _copy(lang, "integrity"), 1)
    _add_bullets(
        doc,
        [
            _copy(lang, "technical_conclusion"),
            str(detail.get("validation_notes") or ""),
            "All intended models executed successfully in the validated run.",
            "Artifact consistency checks confirmed shared run ID and data fingerprint across stored outputs.",
        ]
        + list((review.get("label_reconciliation") or {}).get("limitations") or []),
    )

    _add_heading(doc, _copy(lang, "conclusions"), 1)
    _add_note_box(
        doc,
        _copy(lang, "section_note"),
        _narrative_robust_winner(detail, run_summary, lang),
    )

    _add_heading(doc, _copy(lang, "reproducibility"), 1)
    _add_bullets(
        doc,
        [
            f"Run ID: {run_id}",
            f"Dataset fingerprint: {detail.get('dataset_fingerprint') or 'n/a'}",
            f"Feature schema version: {_humanize_identifier(dataset_summary.get('feature_schema_version') or run_summary.get('feature_schema_version') or 'n/a')}",
            "This report was generated from stored artifacts only; it does not recompute training metrics independently.",
        ],
    )

    _add_heading(doc, _copy(lang, "implementation"), 1)
    _add_note_box(doc, _copy(lang, "section_note"), "Recommendation: maintain current production logic, expand teacher coverage, and revisit only after broader validated evidence is available.")

    _add_heading(doc, _copy(lang, "limitations"), 1)
    limitation_rows = _unique_nonempty(
        list(academic.get("limitations") or [])
        + list(detail.get("limitations") or [])
        + list((review.get("label_reconciliation") or {}).get("limitations") or [])
    )
    _add_bullets(doc, limitation_rows or [t("admin_eic_report_no_additional_risks", lang=lang)])

    _add_heading(doc, _copy(lang, "appendix"), 1)
    _add_heading(doc, _copy(lang, "artifact_manifest"), 2)
    _add_table(
        doc,
        [_copy(lang, "artifact_name"), _copy(lang, "artifact_purpose"), _copy(lang, "artifact_format"), _copy(lang, "artifact_checksum"), _copy(lang, "artifact_availability")],
        manifest_rows,
        [1.5, 2.5, 0.7, 1.0, 1.0],
        caption=_copy(lang, "caption_manifest"),
    )
    for file_name in filenames:
        _add_paragraph(doc, f"{_copy(lang, 'artifact_filename')}: {file_name}", color=MUTED)

    if model_rows:
        _add_landscape_section(doc)
        _apply_page_furniture(doc, _copy(lang, "technical_report_name"), run_id, lang)
        _add_heading(doc, "Full model comparison", 2)
        for title, headers, rows, widths, numeric_cols in _model_metric_groups(model_rows, lang):
            _add_heading(doc, title, 3)
            _add_table(doc, headers, rows, widths, numeric_cols=numeric_cols, caption=_copy(lang, "caption_models"))

    report_dir = _report_dir(run_id, lang)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / _report_filename("technical_docx", run_id)
    doc.save(path)
    return {"ok": True, "path": str(path), "bytes": _verified_docx_bytes(path), "report_type": "technical_docx"}


def build_experiment_report_docx(run_id: str, language: str) -> dict[str, Any]:
    lang = _lang(language)
    technical = build_technical_report_docx(run_id, lang)
    if not technical.get("ok"):
        return technical
    report_dir = _report_dir(run_id, lang)
    report_dir.mkdir(parents=True, exist_ok=True)
    source_path = Path(str(technical.get("path") or ""))
    target_path = report_dir / _report_filename("experiment_docx", run_id)
    target_path.write_bytes(_verified_docx_bytes(source_path))
    return {"ok": True, "path": str(target_path), "bytes": _verified_docx_bytes(target_path), "report_type": "experiment_docx"}


def get_or_create_validated_report(run_id: str, report_type: str, language: str) -> dict[str, Any]:
    safe_type = _clean_text(report_type)
    safe_run_id = _clean_text(run_id)
    lang = _lang(language)
    if safe_type not in REPORT_TYPES:
        return {"ok": False, "message": t("admin_eic_report_generation_failed", lang=lang)}
    path = _report_dir(safe_run_id, lang) / _report_filename(safe_type, safe_run_id)
    if path.exists():
        return {"ok": True, "path": str(path), "bytes": _verified_docx_bytes(path), "report_type": safe_type}
    builders = {
        "experiment_docx": build_experiment_report_docx,
        "executive_docx": build_executive_report_docx,
        "academic_docx": build_academic_report_docx,
        "technical_docx": build_technical_report_docx,
    }
    return builders[safe_type](safe_run_id, lang)


def list_available_eic_reports(run_id: str, user_capabilities: set[str] | None = None, *, language: str = "en") -> list[dict[str, Any]]:
    safe_run_id = _clean_text(run_id)
    lang = _lang(language)
    capabilities = user_capabilities or set()
    detail = _validated_run_detail(safe_run_id)
    has_validated_run = bool(detail)
    base_rows = [
        {
            "report_type": "experiment_docx",
            "title": get_report_type_display("experiment_docx", lang=lang),
            "description": t("admin_eic_report_experiment_subtitle", lang=lang),
            "status": "available" if has_validated_run else "no_validated_run",
            "restricted": False,
        }
    ]
    for row in base_rows:
        if row["status"] == "available":
            path = _report_dir(safe_run_id, lang) / _report_filename(str(row["report_type"]), safe_run_id)
            row["path"] = str(path) if path.exists() else ""
            row["download_ready"] = path.exists()
        else:
            row["path"] = ""
            row["download_ready"] = False
    return base_rows
