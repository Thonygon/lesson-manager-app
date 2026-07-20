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
from services.experiment_report_context_service import get_report_context, report_context_completion
from services import eic_service
from services.ai_usage_service import log_ai_usage_event, with_provider_chain
from services.authorization_service import CAPABILITY_VIEW_TECHNICAL_ARTIFACTS
from services.eic_display_service import (
    get_business_action_display,
    get_component_display_name,
    get_component_text_display,
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
EXPERIMENT_REPORT_TEMPLATE_VERSION = 6
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


def _translated_business_question(detail: dict[str, Any], lang: str) -> str:
    experiment_id = _clean_text(detail.get("experiment_id") or "")
    if experiment_id == "assigned_resource_open_within_7d":
        return get_component_text_display(
            "assigned_resource_open_within_7d",
            "business_question",
            detail.get("business_question"),
            lang=lang,
        )
    if experiment_id == "student_recommendation_open_within_7d":
        fallback = _clean_text(detail.get("business_question"))
        if lang == "es":
            return fallback or "¿Puede Classio predecir si un estudiante abrirá una recomendación opcional dentro de siete días desde que la ve?"
        if lang == "tr":
            return fallback or "Classio, bir öğrencinin isteğe bağlı bir öneriyi gördükten sonraki yedi gün içinde açıp açmayacağını tahmin edebilir mi?"
        return fallback
    return _clean_text(detail.get("business_question"))


def _translate_known_evidence_text(value: Any, lang: str) -> str:
    text = _clean_text(value)
    if not text or lang == "en":
        return text
    replacements = {
        "es": {
            "This run was generated by the current Phase 3.6 pipeline, so historical Phase 3.5 audit-count reconciliation is not required for validation.": "Esta ejecución fue generada por la canalización actual de la Fase 3.6, por lo que la conciliación histórica de conteos de auditoría de la Fase 3.5 no es necesaria para la validación.",
            "No identifier mismatch was found.": "No se detectó ningún desajuste de identificadores.",
            "Missing values are produced by the feature-construction rule that only uses strictly earlier mature history.": "Los valores faltantes se producen por la regla de construcción de variables que solo utiliza historial maduro estrictamente anterior.",
            "For early assignments there is no mature prior history yet; resource-level sparsity is especially severe for prior_resource_open_rate.": "En las asignaciones tempranas todavía no existe historial maduro previo; la dispersión a nivel de recurso es especialmente alta para prior_resource_open_rate.",
        },
        "tr": {
            "This run was generated by the current Phase 3.6 pipeline, so historical Phase 3.5 audit-count reconciliation is not required for validation.": "Bu çalışma mevcut Phase 3.6 hattı tarafından üretildiği için, doğrulama açısından geçmiş Phase 3.5 denetim sayımı uzlaştırması gerekli değildir.",
            "No identifier mismatch was found.": "Kimlik eşleşmesinde bir tutarsızlık bulunmadı.",
            "Missing values are produced by the feature-construction rule that only uses strictly earlier mature history.": "Eksik değerler, yalnızca daha önceki olgun geçmişi kullanan özellik oluşturma kuralından kaynaklanır.",
            "For early assignments there is no mature prior history yet; resource-level sparsity is especially severe for prior_resource_open_rate.": "Erken atamalarda henüz olgun bir önceki geçmiş yoktur; kaynak düzeyindeki seyreklik özellikle prior_resource_open_rate için yüksektir.",
        },
    }
    translated = text
    for source, target in replacements.get(lang, {}).items():
        translated = translated.replace(source, target)
    return translated


def _date_connector(lang: str) -> str:
    if lang == "es":
        return "a"
    if lang == "tr":
        return "-"
    return "to"


def _copy(lang: str, key: str, **kwargs) -> str:
    template = _COPY[_lang(lang)].get(key, _COPY["en"].get(key, key))
    return template.format(**kwargs)


_REPORT_PHRASES: dict[str, dict[str, str]] = {
    "en": {
        "chronological_cutoff": "Chronological cutoff",
        "source_rows": "Source rows",
        "included_rows": "Included rows",
        "positive_labels": "Positive labels",
        "negative_labels": "Negative labels",
        "right_censored": "Right-censored",
        "teachers_represented": "Teachers represented",
        "students_represented": "Students represented",
        "resources_represented": "Resources represented",
        "date_range": "Date range",
        "development_rows": "Development rows",
        "holdout_rows": "Holdout rows",
        "stored_review": "Stored review",
        "past_only": "Past-only",
        "full_model_comparison": "Full model comparison",
        "discrimination_ranking": "Discrimination and ranking",
        "calibration_thresholding": "Calibration and thresholding",
        "runtime_status": "Runtime and status",
        "feature_col": "Feature",
        "source_col": "Source",
        "availability_col": "Availability",
        "prediction_time_availability_col": "Prediction-time availability",
        "overall_missing_col": "Overall missing",
        "dev_missing_col": "Dev missing",
        "holdout_missing_col": "Holdout missing",
        "included_col": "Included",
        "explanation_col": "Explanation",
        "kind_col": "Kind",
        "status_col": "Status",
        "selected_hyperparameters": "Selected hyperparameters",
        "stored_supporting_artifact": "Stored supporting artifact",
        "validated_run_summary": "Validated run summary",
        "dataset_accounting_purpose": "Dataset accounting and counts",
        "stored_model_metrics": "Stored model metrics",
        "stored_holdout_probabilities": "Stored holdout probabilities",
        "feature_availability_audit": "Feature availability audit",
        "label_reconciliation_review": "Label reconciliation review",
        "integrity_narrative": "Integrity narrative",
        "findings_markdown_baseline": "Findings interpretation markdown baseline",
        "technical_markdown_baseline": "Technical markdown baseline",
    },
    "es": {
        "chronological_cutoff": "Corte cronológico",
        "source_rows": "Filas de origen",
        "included_rows": "Filas incluidas",
        "positive_labels": "Etiquetas positivas",
        "negative_labels": "Etiquetas negativas",
        "right_censored": "Censuradas por ventana",
        "teachers_represented": "Docentes representados",
        "students_represented": "Estudiantes representados",
        "resources_represented": "Recursos representados",
        "date_range": "Rango de fechas",
        "development_rows": "Filas de desarrollo",
        "holdout_rows": "Filas de holdout",
        "stored_review": "Revisión almacenada",
        "past_only": "Solo pasado",
        "full_model_comparison": "Comparación completa de modelos",
        "discrimination_ranking": "Discriminación y ranking",
        "calibration_thresholding": "Calibración y umbrales",
        "runtime_status": "Rendimiento y estado",
        "feature_col": "Variable",
        "source_col": "Fuente",
        "availability_col": "Disponibilidad",
        "prediction_time_availability_col": "Disponibilidad al momento de predicción",
        "overall_missing_col": "Falta total",
        "dev_missing_col": "Falta en desarrollo",
        "holdout_missing_col": "Falta en holdout",
        "included_col": "Incluida",
        "explanation_col": "Explicación",
        "kind_col": "Tipo",
        "status_col": "Estado",
        "selected_hyperparameters": "Hiperparámetros seleccionados",
        "stored_supporting_artifact": "Artefacto de soporte almacenado",
        "validated_run_summary": "Resumen de ejecución validada",
        "dataset_accounting_purpose": "Contabilidad y conteos del conjunto de datos",
        "stored_model_metrics": "Métricas de modelo almacenadas",
        "stored_holdout_probabilities": "Probabilidades holdout almacenadas",
        "feature_availability_audit": "Auditoría de disponibilidad de variables",
        "label_reconciliation_review": "Revisión de conciliación de etiquetas",
        "integrity_narrative": "Narrativa de integridad",
        "findings_markdown_baseline": "Base markdown de interpretación de hallazgos",
        "technical_markdown_baseline": "Base markdown técnica",
    },
    "tr": {
        "chronological_cutoff": "Kronolojik kesim",
        "source_rows": "Kaynak satırlar",
        "included_rows": "Dahil edilen satırlar",
        "positive_labels": "Pozitif etiketler",
        "negative_labels": "Negatif etiketler",
        "right_censored": "Sağ sansürlü",
        "teachers_represented": "Temsil edilen öğretmenler",
        "students_represented": "Temsil edilen öğrenciler",
        "resources_represented": "Temsil edilen kaynaklar",
        "date_range": "Tarih aralığı",
        "development_rows": "Geliştirme satırları",
        "holdout_rows": "Holdout satırları",
        "stored_review": "Saklanan inceleme",
        "past_only": "Yalnızca geçmiş",
        "full_model_comparison": "Tam model karşılaştırması",
        "discrimination_ranking": "Ayrıştırma ve sıralama",
        "calibration_thresholding": "Kalibrasyon ve eşikleme",
        "runtime_status": "Çalışma süresi ve durum",
        "feature_col": "Özellik",
        "source_col": "Kaynak",
        "availability_col": "Kullanılabilirlik",
        "prediction_time_availability_col": "Tahmin anı kullanılabilirliği",
        "overall_missing_col": "Genel eksik",
        "dev_missing_col": "Geliştirme eksik",
        "holdout_missing_col": "Holdout eksik",
        "included_col": "Dahil",
        "explanation_col": "Açıklama",
        "kind_col": "Tür",
        "status_col": "Durum",
        "selected_hyperparameters": "Seçilen hiperparametreler",
        "stored_supporting_artifact": "Saklanan destekleyici artefakt",
        "validated_run_summary": "Doğrulanmış çalışma özeti",
        "dataset_accounting_purpose": "Veri kümesi sayımı ve adetler",
        "stored_model_metrics": "Saklanan model metrikleri",
        "stored_holdout_probabilities": "Saklanan holdout olasılıkları",
        "feature_availability_audit": "Özellik kullanılabilirlik denetimi",
        "label_reconciliation_review": "Etiket uzlaştırma incelemesi",
        "integrity_narrative": "Bütünlük anlatısı",
        "findings_markdown_baseline": "Bulgular yorumlama markdown temeli",
        "technical_markdown_baseline": "Teknik markdown temeli",
    },
}


def _phrase(lang: str, key: str) -> str:
    safe_lang = _lang(lang)
    return _REPORT_PHRASES.get(safe_lang, {}).get(key, _REPORT_PHRASES["en"].get(key, key))


def _now_text(lang: str) -> str:
    stamp = datetime.now().astimezone()
    if lang == "es":
        return stamp.strftime("%d/%m/%Y %H:%M")
    if lang == "tr":
        return stamp.strftime("%d.%m.%Y %H:%M")
    return stamp.strftime("%Y-%m-%d %H:%M")


def _format_file_timestamp(path: Path, lang: str) -> str:
    try:
        stamp = datetime.fromtimestamp(path.stat().st_mtime).astimezone()
    except Exception:
        return ""
    if lang == "es":
        return stamp.strftime("%d/%m/%Y %H:%M:%S")
    if lang == "tr":
        return stamp.strftime("%d.%m.%Y %H:%M:%S")
    return stamp.strftime("%Y-%m-%d %H:%M:%S")


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
    experiment_id = str(detail.get("experiment_id") or "")
    academic = eic_service.get_academic_evidence_summary(run_id, cache_bust=f"academic-{run_id}")
    telemetry = eic_service.get_business_telemetry_health(cache_bust=f"telemetry-{run_id}")
    portfolio = eic_service.get_intelligence_component_portfolio(cache_bust=f"portfolio-{run_id}")
    decisions = eic_service.get_prioritized_intelligence_decisions(cache_bust=f"decisions-{run_id}")
    latest_summary = eic_service.get_intelligence_business_summary(cache_bust=f"summary-{run_id}")
    artifacts = _artifact_path_map(run_id)
    run_summary = _read_json(artifacts.get("run_summary_json", Path("__missing__")))
    dataset_summary = _read_json(artifacts.get("dataset_summary_json", Path("__missing__")))
    report_context = get_report_context(run_id, experiment_id, lang)
    return {
        "detail": detail,
        "academic": academic,
        "telemetry": telemetry,
        "portfolio": portfolio,
        "decisions": decisions,
        "latest_summary": latest_summary,
        "run_summary": run_summary,
        "dataset_summary": dataset_summary,
        "report_context": report_context,
        "report_context_completion": report_context_completion(report_context),
        "lang": lang,
    }


def _generate_report_ai_narrative(context: dict[str, Any], *, report_kind: str, lang: str) -> dict[str, Any]:
    try:
        from helpers.lesson_planner import (
            _extract_json_object_from_text,
            _generate_with_gemini,
            _generate_with_openai,
            _generate_with_openrouter,
            get_ai_provider_order,
        )
    except Exception:
        return {}

    detail = context.get("detail") or {}
    academic = context.get("academic") or {}
    run_summary = context.get("run_summary") or {}
    dataset_summary = context.get("dataset_summary") or {}
    evaluation = run_summary.get("evaluation") or {}
    review = run_summary.get("review") or {}

    language_name = {"en": "English", "es": "Spanish", "tr": "Turkish"}.get(_lang(lang), "English")
    system_prompt = (
        "You are Classio's internal experiment reporting analyst. "
        "Return exactly one valid JSON object and nothing else. "
        "Do not use markdown. Do not use code fences. "
        "Write all narrative text in the requested report language. "
        "Be precise, evidence-grounded, concise, and professional. "
        "Do not invent metrics, counts, or causal claims. "
        "If evidence is weak, say so clearly."
    )
    prompt_payload = {
        "report_kind": report_kind,
        "report_language": language_name,
        "experiment": str(detail.get("experiment_id") or ""),
        "run_id": str(detail.get("run_id") or ""),
        "run_status": str(detail.get("run_status") or ""),
        "integrity_status": str(detail.get("integrity_status") or ""),
        "maturity_verdict": str(detail.get("maturity_verdict") or ""),
        "evidence_verdict": str(detail.get("evidence_level") or detail.get("evidence_verdict") or ""),
        "business_question": str(detail.get("business_question") or ""),
        "recommended_business_action": str(detail.get("recommended_business_action") or ""),
        "included_rows": int(detail.get("included_row_count") or dataset_summary.get("included_row_count") or 0),
        "positive_labels": int(detail.get("positive_label_count") or dataset_summary.get("positive_count") or 0),
        "negative_labels": int(detail.get("negative_label_count") or dataset_summary.get("negative_count") or 0),
        "teachers_represented": int(detail.get("teachers_represented") or dataset_summary.get("teacher_count") or 0),
        "students_represented": int(detail.get("students_represented") or dataset_summary.get("student_count") or 0),
        "resources_represented": int(detail.get("resources_represented") or dataset_summary.get("resource_count") or 0),
        "primary_metric_leader": str(evaluation.get("primary_metric_leader") or detail.get("primary_metric_leader") or ""),
        "best_thresholded_classifier": str(evaluation.get("best_thresholded_classifier") or ""),
        "best_precision_recall_ranking": str(evaluation.get("best_precision_recall_ranking") or ""),
        "calibration_leader": str(evaluation.get("calibration_leader") or ""),
        "limitations": _unique_nonempty(list(academic.get("limitations") or []) + list(detail.get("limitations") or []) + list((review.get("label_reconciliation") or {}).get("limitations") or [])),
        "future_work": list(academic.get("future_improvements") or []),
        "validation_notes": str(detail.get("validation_notes") or ""),
        "report_context": context.get("report_context") or {},
    }
    user_prompt = (
        "Create a JSON object with these keys: "
        "analysis_paragraph, conclusion_paragraph, implementation_paragraph, decision_summary_paragraph, non_proof_paragraph, main_limitation_text, proposed_next_action_text, context_rewrites, limitations, future_work. "
        "The context_rewrites field must be an object. Rewrite only the user-provided context values into polished report language for these keys when present: "
        "business_problem, decision_supported, expected_value, product_impact, success_definition, minimum_evidence_required, risks, main_limitation, evidence_non_proof, recommended_next_action, next_review_trigger, next_review_date, responsible_person_or_team, meeting_notes. "
        "The limitations and future_work fields must be arrays of short strings. "
        "Do not invent missing business context. If a context value is missing, leave that key empty in context_rewrites. "
        "Base every statement on this experiment context only:\n"
        + json.dumps(prompt_payload, ensure_ascii=False, indent=2)
    )

    provider_order = get_ai_provider_order()
    log_ai_usage_event(
        "experiment_report_ai",
        "requested",
        with_provider_chain({
            "report_kind": report_kind,
            "language": lang,
            "experiment_id": str(detail.get("experiment_id") or ""),
            "run_id": str(detail.get("run_id") or ""),
        }, provider_order),
    )
    errors: list[str] = []
    for provider in provider_order:
        try:
            if provider == "gemini":
                raw_text = _generate_with_gemini(system_prompt, user_prompt)
            elif provider == "openrouter":
                raw_text = _generate_with_openrouter(system_prompt, user_prompt)
            else:
                raw_text = _generate_with_openai(system_prompt, user_prompt)
            parsed = _extract_json_object_from_text(raw_text)
            if not isinstance(parsed, dict):
                raise ValueError("AI narrative payload was not an object.")
            log_ai_usage_event(
                "experiment_report_ai",
                "success",
                {
                    "report_kind": report_kind,
                    "language": lang,
                    "experiment_id": str(detail.get("experiment_id") or ""),
                    "run_id": str(detail.get("run_id") or ""),
                    "provider": provider,
                },
            )
            return {
                "analysis_paragraph": _clean_text(parsed.get("analysis_paragraph")),
                "conclusion_paragraph": _clean_text(parsed.get("conclusion_paragraph")),
                "implementation_paragraph": _clean_text(parsed.get("implementation_paragraph")),
                "decision_summary_paragraph": _clean_text(parsed.get("decision_summary_paragraph")),
                "non_proof_paragraph": _clean_text(parsed.get("non_proof_paragraph")),
                "main_limitation_text": _clean_text(parsed.get("main_limitation_text")),
                "proposed_next_action_text": _clean_text(parsed.get("proposed_next_action_text")),
                "context_rewrites": dict(parsed.get("context_rewrites") or {}),
                "limitations": _unique_nonempty(list(parsed.get("limitations") or [])),
                "future_work": _unique_nonempty(list(parsed.get("future_work") or [])),
                "_ai_used": True,
                "_provider": provider,
            }
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
    log_ai_usage_event(
        "experiment_report_ai",
        "failed",
        with_provider_chain({
            "report_kind": report_kind,
            "language": lang,
            "experiment_id": str(detail.get("experiment_id") or ""),
            "run_id": str(detail.get("run_id") or ""),
            "errors": errors,
        }, provider_order),
    )
    return {}


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
        if lang == "es":
            return f"{leader} lideró la comparación validada con suficiente solidez como para justificar un shadow testing controlado."
        if lang == "tr":
            return f"{leader}, kontrollü shadow testini haklı çıkaracak kadar güçlü şekilde doğrulanmış karşılaştırmaya liderlik etti."
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
        [_phrase(lang, "chronological_cutoff"), str(detail.get("chronological_cutoff") or evaluation.get("cutoff_timestamp") or "n/a")],
    ]


def _dataset_accounting_rows(detail: dict[str, Any], run_summary: dict[str, Any], dataset_summary: dict[str, Any], lang: str) -> list[list[str]]:
    dataset = run_summary.get("dataset") or dataset_summary
    evaluation = run_summary.get("evaluation") or {}
    rows = [
        [_phrase(lang, "source_rows"), str(dataset.get("source_row_count") or "n/a")],
        [_phrase(lang, "included_rows"), str(dataset.get("included_row_count") or detail.get("included_row_count") or "n/a")],
        [_phrase(lang, "positive_labels"), str(dataset.get("positive_count") or detail.get("positive_label_count") or "n/a")],
        [_phrase(lang, "negative_labels"), str(dataset.get("negative_count") or detail.get("negative_label_count") or "n/a")],
        [_phrase(lang, "right_censored"), str(dataset.get("excluded_row_count") or "0")],
        [_phrase(lang, "teachers_represented"), str(dataset.get("teacher_count") or detail.get("teachers_represented") or "0")],
        [_phrase(lang, "students_represented"), str(dataset.get("student_count") or detail.get("students_represented") or "0")],
        [_phrase(lang, "resources_represented"), str(dataset.get("resource_count") or detail.get("resources_represented") or "0")],
        [_phrase(lang, "date_range"), f"{(dataset.get('date_range') or {}).get('assigned_at_min') or detail.get('source_start_at') or 'n/a'} {_date_connector(lang)} {(dataset.get('date_range') or {}).get('assigned_at_max') or detail.get('source_end_at') or 'n/a'}"],
        [_phrase(lang, "chronological_cutoff"), str(evaluation.get("cutoff_timestamp") or detail.get("chronological_cutoff") or "n/a")],
        [_phrase(lang, "development_rows"), str(evaluation.get("development_count") or "n/a")],
        [_phrase(lang, "holdout_rows"), str(evaluation.get("holdout_count") or "n/a")],
    ]
    for reason, count in (dataset.get("exclusion_reasons") or {}).items():
        if reason == "included":
            continue
        rows.append([f"{_humanize_identifier(reason)}", str(count)])
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
                _phrase(lang, "stored_review"),
                _phrase(lang, "past_only"),
                f"{round(_float(row.get('overall_missing_percentage')), 2)}%",
                f"{round(_float(row.get('development_missing_percentage')), 2)}%",
                f"{round(_float(row.get('holdout_missing_percentage')), 2)}%",
                _bool_text(not row.get("excluded_from_logistic_regression_reduced"), lang),
                _translate_known_evidence_text(row.get("missingness_explanation") or "", lang),
            ]
        )
    return rows


def _model_metric_groups(model_rows: list[dict[str, Any]], lang: str) -> list[tuple[str, list[str], list[list[str]], list[float], set[int]]]:
    group_specs = [
        (
            _phrase(lang, "discrimination_ranking"),
            ["model_name", "roc_auc", "average_precision", "balanced_accuracy", "f1", "delta_vs_dummy_roc_auc"],
            [1, 2, 3, 4, 5],
            [2.2, 1.2, 1.2, 1.2, 1.0, 1.5],
        ),
        (
            _phrase(lang, "calibration_thresholding"),
            ["model_name", "log_loss", "brier_score", "predicted_positive_rate", "best_f1", "best_balanced_accuracy"],
            [1, 2, 3, 4, 5],
            [2.1, 1.2, 1.2, 1.4, 1.0, 1.5],
        ),
        (
            _phrase(lang, "runtime_status"),
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
        "run_summary_json": _phrase(lang, "validated_run_summary"),
        "dataset_summary_json": _phrase(lang, "dataset_accounting_purpose"),
        "model_comparison_csv": _phrase(lang, "stored_model_metrics"),
        "holdout_predictions_csv": _phrase(lang, "stored_holdout_probabilities"),
        "feature_audit_csv": _phrase(lang, "feature_availability_audit"),
        "label_reconciliation_csv": _phrase(lang, "label_reconciliation_review"),
        "integrity_report_md": _phrase(lang, "integrity_narrative"),
        "academic_report_md": _phrase(lang, "findings_markdown_baseline"),
        "findings_interpretation_report_md": _phrase(lang, "findings_markdown_baseline"),
        "technical_report_md": _phrase(lang, "technical_markdown_baseline"),
    }
    rows: list[list[str]] = []
    filenames: list[str] = []
    for artifact_type, path in sorted(artifacts.items()):
        filenames.append(path.name)
        rows.append(
            [
                _artifact_display_name(artifact_type),
                purpose_map.get(artifact_type, _phrase(lang, "stored_supporting_artifact")),
                path.suffix.lstrip(".") or "file",
                _hash_file(path),
                _copy(lang, "yes") if path.exists() else _copy(lang, "no"),
            ]
        )
    return rows, filenames


def _editable_placeholder(lang: str) -> str:
    if lang == "es":
        return "[Por completar por la persona responsable de revisión en Classio.]"
    if lang == "tr":
        return "[Classio'da sorumlu inceleyici tarafından doldurulacak.]"
    return "[To be completed by the responsible Classio reviewer.]"


def _context_label(key: str, lang: str) -> str:
    return t(f"report_context_{key}", lang=lang)


def _context_text(context: dict[str, Any], key: str, lang: str, ai_narrative: dict[str, Any] | None = None) -> str:
    polished = _clean_text((((ai_narrative or {}).get("context_rewrites") or {}).get(key)))
    if polished:
        return polished
    value = _clean_text((context or {}).get(key))
    return value or _editable_placeholder(lang)


def _ai_used_text(ai_narrative: dict[str, Any], lang: str) -> str:
    values: list[str] = []
    for value in (ai_narrative or {}).values():
        if isinstance(value, list):
            continue
        if isinstance(value, dict):
            values.extend(_clean_text(item) for item in value.values())
        else:
            values.append(_clean_text(value))
    return _copy(lang, "yes") if any(values) else _copy(lang, "no")


def _report_context_missing_labels(context: dict[str, Any], lang: str) -> list[str]:
    completion = context.get("report_context_completion") or report_context_completion(context.get("report_context") or context)
    return [_context_label(field, lang) for field in list(completion.get("missing_fields") or [])]


def _scorecard_status(value: str, lang: str) -> str:
    normalized = _clean_text(value).lower()
    labels = {
        "strong": {"en": "Strong", "es": "Fuerte", "tr": "Güçlü"},
        "moderate": {"en": "Moderate", "es": "Moderada", "tr": "Orta"},
        "limited": {"en": "Limited", "es": "Limitada", "tr": "Sınırlı"},
        "insufficient": {"en": "Insufficient", "es": "Insuficiente", "tr": "Yetersiz"},
        "incomplete": {"en": "Incomplete", "es": "Incompleta", "tr": "Incompleta"},
        "not assessed": {"en": "Not assessed", "es": "No evaluada", "tr": "Değerlendirilmedi"},
    }
    return labels.get(normalized, {}).get(lang, value)


def _decision_summary_rows(context: dict[str, Any], ai_narrative: dict[str, Any], lang: str) -> list[list[str]]:
    detail = context.get("detail") or {}
    run_summary = context.get("run_summary") or {}
    report_context = context.get("report_context") or {}
    evaluation = run_summary.get("evaluation") or {}
    limitations = _unique_nonempty(
        list((context.get("academic") or {}).get("limitations") or [])
        + list(detail.get("limitations") or [])
        + list(((run_summary.get("review") or {}).get("label_reconciliation") or {}).get("limitations") or [])
    )
    return [
        [_copy(lang, "meta_field"), _copy(lang, "meta_value")],
        ["Experiment" if lang == "en" else ("Experimento" if lang == "es" else "Deney"), str(detail.get("experiment_id") or "")],
        ["Business problem" if lang == "en" else ("Problema de negocio" if lang == "es" else "İş problemi"), _context_text(report_context, "business_problem", lang, ai_narrative)],
        ["Decision supported" if lang == "en" else ("Decisión apoyada" if lang == "es" else "Desteklenen karar"), _context_text(report_context, "decision_supported", lang, ai_narrative)],
        ["Current evidence status" if lang == "en" else ("Estado actual de la evidencia" if lang == "es" else "Mevcut kanıt durumu"), get_evidence_display(str(detail.get("evidence_level") or detail.get("evidence_verdict") or "not_available"), lang=lang)],
        ["Robust winner" if lang == "en" else ("Ganador robusto" if lang == "es" else "Güçlü kazanan"), _bool_text((detail.get("model_results") or {}).get("robust_winner"), lang)],
        ["Model leader" if lang == "en" else ("Modelo líder" if lang == "es" else "Lider model"), _model_name(str(evaluation.get("primary_metric_leader") or detail.get("primary_metric_leader") or ""), lang)],
        ["Next review trigger" if lang == "en" else ("Disparador de la próxima revisión" if lang == "es" else "Sonraki inceleme tetikleyicisi"), _context_text(report_context, "next_review_trigger", lang, ai_narrative)],
        ["Responsible person or team" if lang == "en" else ("Persona o equipo responsable" if lang == "es" else "Sorumlu kişi veya ekip"), _context_text(report_context, "responsible_person_or_team", lang, ai_narrative)],
        ["Main limitation" if lang == "en" else ("Limitación principal" if lang == "es" else "Ana sınırlama"), _clean_text(ai_narrative.get("main_limitation_text")) or _context_text(report_context, "main_limitation", lang, ai_narrative) or (limitations[0] if limitations else _editable_placeholder(lang))],
    ]


def _readiness_scorecard_rows(context: dict[str, Any], lang: str) -> list[list[str]]:
    detail = context.get("detail") or {}
    run_summary = context.get("run_summary") or {}
    dataset_summary = context.get("dataset_summary") or {}
    completion = context.get("report_context_completion") or {}
    telemetry_summary = ((context.get("telemetry") or {}).get("summary") or {})
    included = int(detail.get("included_row_count") or dataset_summary.get("included_row_count") or 0)
    teachers = int(detail.get("teachers_represented") or dataset_summary.get("teacher_count") or 0)
    feature_health = (run_summary.get("review") or {}).get("feature_health") or []
    has_feature_health = bool(feature_health)
    evidence = str(detail.get("evidence_level") or detail.get("evidence_verdict") or "")
    rows = [
        ["Dimension" if lang == "en" else ("Dimensión" if lang == "es" else "Boyut"), "Status" if lang == "en" else ("Estado" if lang == "es" else "Durum"), _copy(lang, "interpretation")],
        ["Data coverage" if lang == "en" else ("Cobertura de datos" if lang == "es" else "Veri kapsamı"), _scorecard_status("moderate" if included >= 100 else "limited", lang), (f"{included} labels" if lang == "en" else (f"{included} etiquetas" if lang == "es" else f"{included} etiket"))],
        ["Teacher diversity" if lang == "en" else ("Diversidad docente" if lang == "es" else "Öğretmen çeşitliliği"), _scorecard_status("limited" if teachers <= 1 else "moderate", lang), (f"{teachers} teacher(s)" if lang == "en" else (f"{teachers} docente(s)" if lang == "es" else f"{teachers} öğretmen"))],
        ["Feature readiness" if lang == "en" else ("Preparación de variables" if lang == "es" else "Özellik hazırlığı"), _scorecard_status("moderate" if has_feature_health else "not assessed", lang), ("Stored feature audit available." if lang == "en" else ("La auditoría almacenada de variables está disponible." if lang == "es" else "Saklanan özellik denetimi mevcut.")) if has_feature_health else _editable_placeholder(lang)],
        ["Model discrimination" if lang == "en" else ("Discriminación del modelo" if lang == "es" else "Model ayrıştırması"), _scorecard_status("moderate" if evidence in {"exploratory", "validated"} else "insufficient", lang), _narrative_robust_winner(detail, run_summary, lang)],
        ["Calibration" if lang == "en" else ("Calibración" if lang == "es" else "Kalibrasyon"), _scorecard_status("not assessed" if not (run_summary.get("evaluation") or {}).get("calibration_leader") else "moderate", lang), _model_name(str((run_summary.get("evaluation") or {}).get("calibration_leader") or ""), lang) or _editable_placeholder(lang)],
        ["Production readiness" if lang == "en" else ("Preparación para producción" if lang == "es" else "Üretim hazırlığı"), _scorecard_status("insufficient", lang), get_run_status_display(str(detail.get("run_status") or ""), lang=lang)],
        ["Business-context completeness" if lang == "en" else ("Completitud del contexto de negocio" if lang == "es" else "İş bağlamı bütünlüğü"), _scorecard_status("moderate" if bool(completion.get("complete")) else "incomplete", lang), f"{int(completion.get('completed_fields') or 0)}/{int(completion.get('total_fields') or 0)}"],
    ]
    if int(telemetry_summary.get("unmatched_opens") or 0) > 0:
        rows.append(["Telemetry quality" if lang == "en" else ("Calidad de telemetría" if lang == "es" else "Telemetri kalitesi"), _scorecard_status("limited", lang), (f"{int(telemetry_summary.get('unmatched_opens') or 0)} unmatched opens" if lang == "en" else (f"{int(telemetry_summary.get('unmatched_opens') or 0)} aperturas sin emparejar" if lang == "es" else f"{int(telemetry_summary.get('unmatched_opens') or 0)} eşleşmeyen açılma"))])
    return rows


def _action_plan_rows(context: dict[str, Any], lang: str) -> list[list[str]]:
    detail = context.get("detail") or {}
    report_context = context.get("report_context") or {}
    run_summary = context.get("run_summary") or {}
    dataset_summary = context.get("dataset_summary") or {}
    teachers = int(detail.get("teachers_represented") or dataset_summary.get("teacher_count") or 0)
    included = int(detail.get("included_row_count") or dataset_summary.get("included_row_count") or 0)
    rows = [[
        _copy(lang, "priority"),
        "Action" if lang == "en" else ("Acción" if lang == "es" else "Eylem"),
        "Reason" if lang == "en" else ("Razón" if lang == "es" else "Gerekçe"),
        _copy(lang, "owner"),
        "Trigger or deadline" if lang == "en" else ("Disparador o fecha" if lang == "es" else "Tetikleyici veya tarih"),
        _phrase(lang, "status_col"),
    ]]
    owner = _context_text(report_context, "responsible_person_or_team", lang)
    if teachers <= 1:
        rows.append(["High", "Expand teacher coverage" if lang == "en" else ("Ampliar cobertura docente" if lang == "es" else "Öğretmen kapsamını genişlet"), "Current evidence comes from one teacher." if lang == "en" else ("La evidencia actual proviene de un solo docente." if lang == "es" else "Mevcut kanıt tek bir öğretmenden geliyor."), owner, "At least five teachers represented" if lang == "en" else ("Al menos cinco docentes representados" if lang == "es" else "En az beş öğretmen temsil edildiğinde"), "Open" if lang == "en" else ("Abierto" if lang == "es" else "Açık")])
    if included < 500:
        rows.append(["Medium", "Continue collecting labels" if lang == "en" else ("Continuar recolectando etiquetas" if lang == "es" else "Etiket toplamaya devam et"), "Current validated sample is still limited." if lang == "en" else ("La muestra validada actual todavía es limitada." if lang == "es" else "Mevcut doğrulanmış örneklem hâlâ sınırlı."), owner, "500 additional mature labels" if lang == "en" else ("500 etiquetas maduras adicionales" if lang == "es" else "500 ek olgun etiket"), "Open" if lang == "en" else ("Abierto" if lang == "es" else "Açık")])
    rows.append(["Medium", "Regenerate report after context review" if lang == "en" else ("Regenerar informe tras revisar el contexto" if lang == "es" else "Bağlam gözden geçirildikten sonra raporu yeniden üret"), "Business context improves meeting readiness." if lang == "en" else ("El contexto de negocio mejora la preparación para reuniones." if lang == "es" else "İş bağlamı toplantı hazırlığını güçlendirir."), owner, _context_text(report_context, "next_review_trigger", lang), "Open" if lang == "en" else ("Abierto" if lang == "es" else "Açık")])
    return rows


def _meeting_notes_rows(report_context: dict[str, Any], lang: str) -> list[list[str]]:
    return [
        [_copy(lang, "meta_field"), _copy(lang, "meta_value")],
        ["Proposed decision" if lang == "en" else ("Decisión propuesta" if lang == "es" else "Önerilen karar"), _context_text(report_context, "decision_supported", lang)],
        ["Decision owner" if lang == "en" else ("Responsable de la decisión" if lang == "es" else "Karar sahibi"), _context_text(report_context, "responsible_person_or_team", lang)],
        ["Review date" if lang == "en" else ("Fecha de revisión" if lang == "es" else "İnceleme tarihi"), _context_text(report_context, "next_review_date", lang)],
        ["Additional comments" if lang == "en" else ("Comentarios adicionales" if lang == "es" else "Ek yorumlar"), _context_text(report_context, "meeting_notes", lang)],
    ]


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
        [_copy(lang, "what_was_evaluated"), _translated_business_question(detail, lang)],
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
        "Next review milestone" if lang == "en" else ("Próximo hito de revisión" if lang == "es" else "Sonraki inceleme kilometre taşı"),
        "Review again after broader teacher coverage is available or when repeated validated runs show stable evidence with cleaner telemetry matching."
        if lang == "en"
        else (
            "Volver a revisar cuando exista una cobertura docente más amplia o cuando ejecuciones validadas repetidas muestren evidencia estable con una telemetría mejor conciliada."
            if lang == "es"
            else "Daha geniş öğretmen kapsamı mevcut olduğunda veya yinelenen doğrulanmış çalışmalar daha temiz telemetri eşleşmesiyle istikrarlı kanıt gösterdiğinde yeniden inceleyin."
        ),
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
    ai_narrative = _generate_report_ai_narrative(context, report_kind="academic", lang=lang)

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
        (_copy(lang, "problem_statement"), _copy(lang, "exec_intro")),
        (_copy(lang, "solution_statement"), _copy(lang, "exec_replace_hold")),
        (_copy(lang, "smart_objective"), _copy(lang, "exec_missing")),
        (_copy(lang, "supervised_formulation"), str(academic.get("target_definition") or "")),
    ]
    for heading, body in academic_sections:
        _add_heading(doc, heading, 1)
        _add_paragraph(doc, body)

    _add_heading(doc, _copy(lang, "dataset_sources"), 1)
    dataset_rows = [
        [_copy(lang, "cover_fingerprint", value="").split(":")[0], str(academic.get("dataset_fingerprint") or "")],
        [_phrase(lang, "dataset_size"), str(academic.get("dataset_size") or 0)],
        ["Positive class balance" if lang == "en" else ("Balance de clase positiva" if lang == "es" else "Pozitif sınıf dengesi"), _pct(academic.get("class_balance") or 0.0)],
        ["Date coverage" if lang == "en" else ("Cobertura temporal" if lang == "es" else "Tarih kapsamı"), f"{(academic.get('date_range') or {}).get('start') or 'n/a'} {_date_connector(lang)} {(academic.get('date_range') or {}).get('end') or 'n/a'}"],
        ["Data sources" if lang == "en" else ("Fuentes de datos" if lang == "es" else "Veri kaynakları"), ", ".join(academic.get("data_sources") or [])],
        ["Unit of analysis" if lang == "en" else ("Unidad de análisis" if lang == "es" else "Analiz birimi"), str(academic.get("unit_of_analysis") or "")],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], dataset_rows, [2.0, 4.7])
    _add_picture_with_caption(doc, charts.get("label_balance", Path("__missing__")), "Figure 1. Stored class distribution for the validated run." if lang == "en" else ("Figura 1. Distribución de clases almacenada para la ejecución validada." if lang == "es" else "Şekil 1. Doğrulanmış çalışma için saklanan sınıf dağılımı."), width=5.6)
    _add_picture_with_caption(doc, charts.get("split_timeline", Path("__missing__")), "Figure 2. Event timeline with the stored chronological cutoff." if lang == "en" else ("Figura 2. Línea temporal de eventos con el corte cronológico almacenado." if lang == "es" else "Şekil 2. Saklanan kronolojik kesim ile olay zaman çizelgesi."), width=6.4)

    _add_heading(doc, _copy(lang, "data_preparation"), 1)
    _add_bullets(
        doc,
        [
            "Inclusion and exclusion rules are taken from the stored dataset summary and the run review." if lang == "en" else ("Las reglas de inclusión y exclusión se toman del resumen de datos y de la revisión almacenada de la ejecución." if lang == "es" else "Dahil etme ve hariç tutma kuralları, saklanan veri kümesi özeti ve çalışma incelemesinden alınır."),
            (f"Included rows: {dataset_summary.get('included_row_count') or detail.get('included_row_count') or 0}." if lang == "en" else (f"Filas incluidas: {dataset_summary.get('included_row_count') or detail.get('included_row_count') or 0}." if lang == "es" else f"Dahil edilen satırlar: {dataset_summary.get('included_row_count') or detail.get('included_row_count') or 0}.")),
            (f"Excluded rows: {dataset_summary.get('excluded_row_count') or 0}, primarily due to open observation windows." if lang == "en" else (f"Filas excluidas: {dataset_summary.get('excluded_row_count') or 0}, principalmente por ventanas de observación abiertas." if lang == "es" else f"Hariç tutulan satırlar: {dataset_summary.get('excluded_row_count') or 0}; bunun başlıca nedeni açık gözlem pencereleridir.")),
            "Right censoring is handled by excluding records whose seven-day observation window had not closed at extraction time." if lang == "en" else ("La censura por la derecha se maneja excluyendo registros cuya ventana de observación de siete días aún no había cerrado al momento de la extracción." if lang == "es" else "Sağ sansürleme, çıkarım anında yedi günlük gözlem penceresi kapanmamış kayıtların dışarıda bırakılmasıyla uygulanır."),
            "Feature engineering is restricted to information available at or before assignment time to avoid leakage." if lang == "en" else ("La ingeniería de variables se restringe a información disponible en o antes del momento de la asignación para evitar fuga de información." if lang == "es" else "Bilgi sızıntısını önlemek için özellik mühendisliği yalnızca atama anında veya öncesinde mevcut olan bilgilerle sınırlandırılır."),
        ],
    )

    _add_heading(doc, _copy(lang, "feature_selection"), 1)
    feature_health = _feature_health_rows(run_summary, lang)
    if feature_health:
        _add_table(
            doc,
            [_phrase(lang, "feature_col"), _phrase(lang, "source_col"), _phrase(lang, "prediction_time_availability_col"), _phrase(lang, "overall_missing_col"), _phrase(lang, "dev_missing_col"), _phrase(lang, "holdout_missing_col"), _phrase(lang, "included_col"), _phrase(lang, "explanation_col")],
            feature_health,
            [0.75, 0.75, 0.9, 0.65, 0.65, 0.75, 0.5, 1.75],
            caption=_copy(lang, "caption_feature_health"),
        )

    _add_heading(doc, _copy(lang, "target_construction"), 1)
    _add_paragraph(doc, "The target is opened_within_7d, derived from teacher_assignments.assigned_at and subsequent opened_at or viewed_at events inside a seven-day window. Negative cases are records whose observation window closed without a qualifying open event." if lang == "en" else ("El objetivo es opened_within_7d, derivado de teacher_assignments.assigned_at y de eventos posteriores opened_at o viewed_at dentro de una ventana de siete días. Los casos negativos son registros cuya ventana de observación cerró sin un evento de apertura válido." if lang == "es" else "Hedef opened_within_7d olup teacher_assignments.assigned_at ve sonraki yedi günlük penceredeki opened_at veya viewed_at olaylarından türetilir. Negatif vakalar, geçerli bir açılma olayı olmadan gözlem penceresi kapanan kayıtlardır."))

    _add_heading(doc, _copy(lang, "methodology"), 1)
    methodology_rows = [
        [_phrase(lang, "chronological_cutoff"), str((academic.get("train_holdout_split") or {}).get("chronological_cutoff") or evaluation.get("cutoff_timestamp") or "n/a")],
        ["Evaluation design" if lang == "en" else ("Diseño de evaluación" if lang == "es" else "Değerlendirme tasarımı"), str(academic.get("evaluation_design") or "")],
        ["Baseline comparator" if lang == "en" else ("Comparador base" if lang == "es" else "Temel karşılaştırıcı"), str(academic.get("baseline") or "DummyClassifier")],
        ["Primary metric leader" if lang == "en" else ("Líder de métrica principal" if lang == "es" else "Ana metrik lideri"), _model_name(str(academic.get("selected_metric_leader") or detail.get("primary_metric_leader") or ""), lang)],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], methodology_rows, [2.0, 4.7])

    _add_heading(doc, _copy(lang, "models_evaluated"), 1)
    model_summary_rows = [
        [
            str(row.get("model_name") or ""),
            str(get_model_comparison_value_display("model_kind", row.get("model_kind"), lang=lang) or ""),
            str(get_model_comparison_value_display("status", row.get("status"), lang=lang) or ""),
            str(row.get("overall_interpretation") or ("Stored comparison available." if lang == "en" else ("Comparación almacenada disponible." if lang == "es" else "Saklanan karşılaştırma mevcut."))),
        ]
        for row in model_rows
    ]
    _add_table(doc, [_copy(lang, "model"), _phrase(lang, "kind_col"), _phrase(lang, "status_col"), _copy(lang, "interpretation")], model_summary_rows, [1.5, 0.8, 0.8, 2.8], caption=_copy(lang, "caption_models"))

    _add_heading(doc, _copy(lang, "evaluation_metrics"), 1)
    _add_bullets(
        doc,
        [
            "Primary ranking metrics: ROC AUC and average precision." if lang == "en" else ("Métricas principales de ranking: ROC AUC y average precision." if lang == "es" else "Ana sıralama metrikleri: ROC AUC ve average precision."),
            "Decision metrics: balanced accuracy, precision, recall, specificity, and F1-score." if lang == "en" else ("Métricas de decisión: balanced accuracy, precision, recall, specificity y F1-score." if lang == "es" else "Karar metrikleri: balanced accuracy, precision, recall, specificity ve F1-score."),
            "Calibration diagnostics: Brier score and log loss." if lang == "en" else ("Diagnósticos de calibración: Brier score y log loss." if lang == "es" else "Kalibrasyon tanıları: Brier score ve log loss."),
            "Confidence intervals are taken from the stored model comparison artifact when available." if lang == "en" else ("Los intervalos de confianza se toman del artefacto almacenado de comparación de modelos cuando está disponible." if lang == "es" else "Güven aralıkları mevcut olduğunda saklanan model karşılaştırma artefaktından alınır."),
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
    _add_paragraph(doc, str(ai_narrative.get("analysis_paragraph") or _narrative_robust_winner(detail, run_summary, lang)))
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
    _add_note_box(doc, _copy(lang, "section_note"), str(ai_narrative.get("conclusion_paragraph") or _copy(lang, "academic_conclusion")))

    _add_heading(doc, _copy(lang, "implementation"), 1)
    _add_paragraph(doc, str(ai_narrative.get("implementation_paragraph") or ("The present evidence supports continued offline evaluation, telemetry improvement, and internal academic review rather than immediate live replacement of the existing heuristic workflow." if lang == "en" else ("La evidencia actual respalda continuar con evaluación offline, mejora de telemetría y revisión académica interna antes de cualquier sustitución inmediata de la lógica heurística en vivo." if lang == "es" else "Mevcut kanıt, canlı sezgisel iş akışının hemen değiştirilmesi yerine çevrimdışı değerlendirme, telemetri iyileştirmesi ve iç akademik incelemenin sürdürülmesini destekler."))))

    _add_heading(doc, _copy(lang, "limitations"), 1)
    _add_bullets(doc, list(ai_narrative.get("limitations") or academic.get("limitations") or detail.get("limitations") or []))

    _add_heading(doc, _copy(lang, "future_work"), 1)
    _add_bullets(doc, list(ai_narrative.get("future_work") or academic.get("future_improvements") or []))

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
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], _dataset_accounting_rows(detail, run_summary, dataset_summary, lang), [2.2, 4.5])

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
    missing_context_labels = _report_context_missing_labels(context, lang)
    if missing_context_labels:
        return {
            "ok": False,
            "message": t("report_context_generation_blocked", lang=lang, fields=", ".join(missing_context_labels)),
        }
    artifacts = _artifact_path_map(run_id)
    if not _required_artifacts_present("technical_docx", context, artifacts):
        return {"ok": False, "message": t("admin_eic_report_unavailable_no_validated_run", lang=lang)}
    detail = context["detail"]
    academic = context["academic"]
    run_summary = context["run_summary"]
    dataset_summary = context["dataset_summary"]
    evaluation = run_summary.get("evaluation") or {}
    review = run_summary.get("review") or {}
    report_context = context.get("report_context") or {}
    charts = _report_chart_assets("technical_docx", run_id, lang, context)
    model_rows = list((detail.get("model_results") or {}).get("models_compared") or [])
    manifest_rows, filenames = _artifact_manifest_rows(artifacts, lang)
    ai_narrative = _generate_report_ai_narrative(context, report_kind="technical", lang=lang)

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

    _add_heading(doc, "Decision Summary" if lang == "en" else ("Resumen de decisión" if lang == "es" else "Karar özeti"), 1)
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], _decision_summary_rows(context, ai_narrative, lang)[1:], [2.4, 4.3])
    if _clean_text(ai_narrative.get("decision_summary_paragraph")):
        _add_note_box(
            doc,
            _copy(lang, "section_note"),
            str(ai_narrative.get("decision_summary_paragraph") or ""),
        )
    _add_note_box(
        doc,
        "What the evidence says" if lang == "en" else ("Qué dice la evidencia" if lang == "es" else "Kanıt ne söylüyor"),
        str(ai_narrative.get("analysis_paragraph") or _narrative_robust_winner(detail, run_summary, lang)),
    )
    _add_note_box(
        doc,
        "What it does not prove" if lang == "en" else ("Qué no demuestra" if lang == "es" else "Ne kanıtlamıyor"),
        str(
            ai_narrative.get("non_proof_paragraph")
            or _context_text(report_context, "evidence_non_proof", lang, ai_narrative)
            or (_unique_nonempty(list(academic.get("limitations") or []) + list(detail.get("limitations") or [])) or [_editable_placeholder(lang)])[0]
        ),
    )
    _add_note_box(
        doc,
        "What Classio should do next" if lang == "en" else ("Qué debe hacer Classio después" if lang == "es" else "Classio'nun sıradaki adımı"),
        str(ai_narrative.get("implementation_paragraph") or ai_narrative.get("proposed_next_action_text") or _context_text(report_context, "recommended_next_action", lang, ai_narrative) or get_business_action_display(str(detail.get("recommended_business_action") or ""), lang=lang) or _editable_placeholder(lang)),
    )

    _add_heading(doc, "Business and educational context" if lang == "en" else ("Contexto de negocio y educativo" if lang == "es" else "İş ve eğitim bağlamı"), 1)
    context_rows = [
        [_copy(lang, "meta_field"), _copy(lang, "meta_value")],
        ["Why this experiment is being evaluated" if lang == "en" else ("Por qué se está evaluando este experimento" if lang == "es" else "Bu deney neden değerlendiriliyor"), _context_text(report_context, "business_problem", lang, ai_narrative)],
        ["Decision supported" if lang == "en" else ("Decisión apoyada" if lang == "es" else "Desteklenen karar"), _context_text(report_context, "decision_supported", lang, ai_narrative)],
        ["Expected value" if lang == "en" else ("Valor esperado" if lang == "es" else "Beklenen değer"), _context_text(report_context, "expected_value", lang, ai_narrative)],
        ["Product impact" if lang == "en" else ("Impacto en producto" if lang == "es" else "Ürün etkisi"), _context_text(report_context, "product_impact", lang, ai_narrative)],
        ["Success definition" if lang == "en" else ("Definición de éxito" if lang == "es" else "Başarı tanımı"), _context_text(report_context, "success_definition", lang, ai_narrative)],
        ["Minimum evidence required" if lang == "en" else ("Evidencia mínima requerida" if lang == "es" else "Gerekli asgari kanıt"), _context_text(report_context, "minimum_evidence_required", lang, ai_narrative)],
        ["Risks" if lang == "en" else ("Riesgos" if lang == "es" else "Riskler"), _context_text(report_context, "risks", lang, ai_narrative)],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], context_rows[1:], [2.3, 4.4])

    _add_heading(doc, "Business readiness scorecard" if lang == "en" else ("Scorecard de preparación de negocio" if lang == "es" else "İş hazırlık puan kartı"), 1)
    scorecard_rows = _readiness_scorecard_rows(context, lang)
    _add_table(doc, scorecard_rows[0], scorecard_rows[1:], [1.6, 1.0, 4.1])

    _add_heading(doc, "Action plan" if lang == "en" else ("Plan de acción" if lang == "es" else "Eylem planı"), 1)
    action_rows = _action_plan_rows(context, lang)
    _add_table(doc, action_rows[0], action_rows[1:], [0.8, 1.7, 2.0, 1.2, 1.5, 0.8])

    _add_heading(doc, _copy(lang, "technical_metadata"), 1)
    metadata_rows = _metadata_rows(detail, run_summary, dataset_summary, lang)[1:]
    metadata_rows.extend(
        [
            ["Business context supplied by" if lang == "en" else ("Contexto de negocio aportado por" if lang == "es" else "İş bağlamını sağlayan"), _clean_text(report_context.get("created_by")) or _editable_placeholder(lang)],
            ["Context last updated" if lang == "en" else ("Última actualización del contexto" if lang == "es" else "Bağlamın son güncellemesi"), _clean_text(report_context.get("updated_at")) or _editable_placeholder(lang)],
            ["AI-assisted wording" if lang == "en" else ("Redacción asistida por IA" if lang == "es" else "YZ destekli ifade"), _ai_used_text(ai_narrative, lang)],
            ["Report language" if lang == "en" else ("Idioma del informe" if lang == "es" else "Rapor dili"), lang.upper()],
            ["Report version" if lang == "en" else ("Versión del informe" if lang == "es" else "Rapor sürümü"), str(EXPERIMENT_REPORT_TEMPLATE_VERSION)],
        ]
    )
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], metadata_rows, [2.2, 4.5])

    _add_heading(doc, _copy(lang, "experiment_definition"), 1)
    _add_paragraph(doc, _translated_business_question(detail, lang))
    _add_paragraph(doc, "Prediction target: opened_within_7d, based on assignment-open behavior within a seven-day window." if lang == "en" else ("Objetivo de predicción: opened_within_7d, basado en comportamiento de apertura de asignaciones dentro de una ventana de siete días." if lang == "es" else "Tahmin hedefi: opened_within_7d; yedi günlük pencere içindeki atama-açılma davranışına dayanır."))

    _add_heading(doc, _copy(lang, "source_logic"), 1)
    _add_bullets(
        doc,
        [
            "Source tables: teacher_assignments, teacher_assignment_attempts, practice_sessions, resource_exposures, and resource_exposure_events." if lang == "en" else ("Tablas fuente: teacher_assignments, teacher_assignment_attempts, practice_sessions, resource_exposures y resource_exposure_events." if lang == "es" else "Kaynak tablolar: teacher_assignments, teacher_assignment_attempts, practice_sessions, resource_exposures ve resource_exposure_events."),
            "Extraction logic is frozen in the validated run artifacts and summarized in the dataset summary JSON." if lang == "en" else ("La lógica de extracción queda congelada en los artefactos validados de la ejecución y se resume en el JSON de resumen del conjunto de datos." if lang == "es" else "Çıkarım mantığı doğrulanmış çalışma artefaktlarında dondurulmuştur ve veri kümesi özeti JSON dosyasında özetlenir."),
            "All feature construction is constrained to information known at or before assignment time." if lang == "en" else ("Toda la construcción de variables se limita a información conocida en o antes del momento de la asignación." if lang == "es" else "Tüm özellik oluşturma yalnızca atama anında veya öncesinde bilinen bilgilerle sınırlandırılmıştır."),
        ],
    )

    _add_heading(doc, _copy(lang, "dataset_accounting"), 1)
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], _dataset_accounting_rows(detail, run_summary, dataset_summary, lang), [2.1, 4.6])
    _add_picture_with_caption(doc, charts.get("label_balance", Path("__missing__")), "Figure 1. Stored target/class distribution." if lang == "en" else ("Figura 1. Distribución almacenada de objetivo y clases." if lang == "es" else "Şekil 1. Saklanan hedef/sınıf dağılımı."), width=5.6)
    _add_picture_with_caption(doc, charts.get("split_timeline", Path("__missing__")), "Figure 2. Assignment timeline and chronological split cutoff." if lang == "en" else ("Figura 2. Línea temporal de asignaciones y corte cronológico." if lang == "es" else "Şekil 2. Atama zaman çizelgesi ve kronolojik ayrım kesimi."), width=6.4)

    _add_heading(doc, _copy(lang, "label_reconciliation"), 1)
    reconciliation = (review.get("label_reconciliation") or {})
    recon_rows = [
        ["Final verdict" if lang == "en" else ("Veredicto final" if lang == "es" else "Nihai hüküm"), get_run_status_display(str(review.get("final_verdict") or detail.get("run_status") or ""), lang=lang)],
        ["Exact row-level reconciliation" if lang == "en" else ("Conciliación exacta a nivel de fila" if lang == "es" else "Satır düzeyinde tam uzlaştırma"), _bool_text(reconciliation.get("exact_row_level_reconciliation_available"), lang)],
        ["Legacy audit reconciliation applicable" if lang == "en" else ("Conciliación de auditoría legacy aplicable" if lang == "es" else "Eski denetim uzlaştırması uygulanabilir"), _bool_text(reconciliation.get("legacy_audit_reconciliation_applicable"), lang)],
        ["Audit counts" if lang == "en" else ("Conteos de auditoría" if lang == "es" else "Denetim sayıları"), json.dumps(reconciliation.get("audit_documented_counts") or {}, ensure_ascii=True)],
        ["Phase 3 counts" if lang == "en" else ("Conteos fase 3" if lang == "es" else "Faz 3 sayıları"), json.dumps(reconciliation.get("phase3_counts") or {}, ensure_ascii=True)],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], recon_rows, [2.4, 4.3])
    _add_bullets(
        doc,
        [
            _translate_known_evidence_text(reconciliation.get("likely_difference_explanation") or "", lang),
            _translate_known_evidence_text(detail.get("validation_notes") or "", lang),
        ],
    )

    _add_heading(doc, _copy(lang, "leakage_controls"), 1)
    _add_bullets(
        doc,
        [
            "Chronological holdout keeps future assignments out of development data." if lang == "en" else ("El holdout cronológico mantiene asignaciones futuras fuera de los datos de desarrollo." if lang == "es" else "Kronolojik holdout, gelecekteki atamaları geliştirme verisinin dışında tutar."),
            "Feature timestamps are checked against assignment time to enforce past-only availability." if lang == "en" else ("Las marcas de tiempo de las variables se comparan con la fecha de asignación para garantizar disponibilidad solo del pasado." if lang == "es" else "Özellik zaman damgaları, yalnızca geçmişte mevcut olan bilgilerin kullanıldığını doğrulamak için atama zamanı ile karşılaştırılır."),
            "Feature missingness explanations in the stored review confirm that sparsity comes from history availability rather than identifier mismatch." if lang == "en" else ("Las explicaciones de ausencia de variables en la revisión almacenada indican que la dispersión proviene de la disponibilidad histórica y no de un desajuste de identificadores." if lang == "es" else "Saklanan incelemedeki özellik eksikliği açıklamaları, seyrekliğin kimlik uyuşmazlığından değil geçmiş veri kullanılabilirliğinden kaynaklandığını doğrular."),
        ],
    )

    _add_heading(doc, _copy(lang, "feature_health"), 1)
    _add_picture_with_caption(doc, charts.get("feature_missingness", Path("__missing__")), "Figure 3. Highest overall missingness rates from the stored feature audit." if lang == "en" else ("Figura 3. Tasas de ausencia más altas según la auditoría almacenada de variables." if lang == "es" else "Şekil 3. Saklanan özellik denetimine göre en yüksek genel eksiklik oranları."), width=6.4)
    feature_health_rows = _feature_health_rows(run_summary, lang)
    if feature_health_rows:
        _add_table(
            doc,
            [_phrase(lang, "feature_col"), _phrase(lang, "source_col"), _phrase(lang, "availability_col"), _phrase(lang, "overall_missing_col"), _phrase(lang, "dev_missing_col"), _phrase(lang, "holdout_missing_col"), _phrase(lang, "included_col"), _phrase(lang, "explanation_col")],
            feature_health_rows,
            [0.75, 0.75, 0.85, 0.65, 0.65, 0.75, 0.5, 2.2],
            caption=_copy(lang, "caption_feature_health"),
        )

    _add_heading(doc, _copy(lang, "preprocessing"), 1)
    _add_bullets(
        doc,
        [
            "Missing values are imputed only when the stored evaluation pipeline marked the feature as retained." if lang == "en" else ("Los valores faltantes se imputan solo cuando la canalización almacenada de evaluación marcó la variable como retenida." if lang == "es" else "Eksik değerler yalnızca saklanan değerlendirme hattı ilgili özelliği korunmuş olarak işaretlediğinde doldurulur."),
            "Categorical features are encoded within the stored pipeline configuration; no report-time transformation modifies model outcomes." if lang == "en" else ("Las variables categóricas se codifican dentro de la configuración almacenada de la canalización; ninguna transformación en tiempo de informe modifica los resultados del modelo." if lang == "es" else "Kategorik özellikler saklanan hat yapılandırması içinde kodlanır; rapor üretimi sırasında yapılan hiçbir dönüşüm model sonuçlarını değiştirmez."),
            "Fully missing development-slice features are automatically excluded before fitting, as documented in the integrity review." if lang == "en" else ("Las variables totalmente ausentes en el tramo de desarrollo se excluyen automáticamente antes del ajuste, tal como se documenta en la revisión de integridad." if lang == "es" else "Geliştirme bölümünde tamamen eksik olan özellikler, bütünlük incelemesinde belgelendiği gibi eğitimden önce otomatik olarak hariç tutulur."),
        ],
    )

    _add_heading(doc, _copy(lang, "cv_section"), 1)
    _add_bullets(
        doc,
        [
            (f"Development rows: {evaluation.get('development_count') or 'n/a'} with {evaluation.get('development_positive_count') or 'n/a'} positives." if lang == "en" else (f"Filas de desarrollo: {evaluation.get('development_count') or 'n/a'} con {evaluation.get('development_positive_count') or 'n/a'} positivas." if lang == "es" else f"Geliştirme satırları: {evaluation.get('development_count') or 'n/a'}; pozitif sayısı {evaluation.get('development_positive_count') or 'n/a'}.")),
            (f"Holdout rows: {evaluation.get('holdout_count') or 'n/a'} with {evaluation.get('holdout_positive_count') or 'n/a'} positives." if lang == "en" else (f"Filas holdout: {evaluation.get('holdout_count') or 'n/a'} con {evaluation.get('holdout_positive_count') or 'n/a'} positivas." if lang == "es" else f"Holdout satırları: {evaluation.get('holdout_count') or 'n/a'}; pozitif sayısı {evaluation.get('holdout_positive_count') or 'n/a'}.")),
            "Cross-validation fold counts and mean metrics are read directly from the stored model comparison artifact." if lang == "en" else ("Los conteos de folds y las métricas medias de validación cruzada se leen directamente del artefacto almacenado de comparación de modelos." if lang == "es" else "Çapraz doğrulama fold sayıları ve ortalama metrikler doğrudan saklanan model karşılaştırma artefaktından okunur."),
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
    _add_table(doc, [_copy(lang, "model"), _phrase(lang, "status_col"), _phrase(lang, "selected_hyperparameters")], config_rows, [1.8, 0.9, 4.0])

    _add_heading(doc, _copy(lang, "baseline_results"), 1)
    _add_picture_with_caption(doc, charts.get("model_metrics", Path("__missing__")), "Figure 4. Model metric comparison snapshot using stored ROC AUC values." if lang == "en" else ("Figura 4. Comparación de métricas de modelos con valores ROC AUC almacenados." if lang == "es" else "Şekil 4. Saklanan ROC AUC değerleriyle model metrik karşılaştırması."), width=6.6)
    _add_picture_with_caption(doc, charts.get("runtime", Path("__missing__")), "Figure 5. Training-runtime comparison from stored model outputs." if lang == "en" else ("Figura 5. Comparación de tiempos de entrenamiento a partir de salidas almacenadas del modelo." if lang == "es" else "Şekil 5. Saklanan model çıktılarından eğitim süresi karşılaştırması."), width=6.6)

    _add_heading(doc, _copy(lang, "threshold_analysis"), 1)
    threshold_rows = [
        ["Primary ROC leader" if lang == "en" else ("Líder principal por ROC" if lang == "es" else "Birincil ROC lideri"), _model_name(str(evaluation.get("primary_metric_leader") or detail.get("primary_metric_leader") or ""), lang)],
        ["Best thresholded classifier" if lang == "en" else ("Mejor clasificador por umbral" if lang == "es" else "En iyi eşiklenmiş sınıflandırıcı"), _model_name(str(evaluation.get("best_thresholded_classifier") or ""), lang)],
        ["Calibration leader" if lang == "en" else ("Líder de calibración" if lang == "es" else "Kalibrasyon lideri"), _model_name(str(evaluation.get("calibration_leader") or ""), lang)],
        ["Best precision-recall ranking" if lang == "en" else ("Mejor ranking precision-recall" if lang == "es" else "En iyi precision-recall sıralaması"), _model_name(str(evaluation.get("best_precision_recall_ranking") or ""), lang)],
    ]
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], threshold_rows, [2.4, 4.3])

    confusion_targets = [
        ("baseline_confusion", "Figure 6. Confusion matrix for the stored baseline." if lang == "en" else ("Figura 6. Matriz de confusión para la línea base almacenada." if lang == "es" else "Şekil 6. Saklanan temel model için karmaşıklık matrisi."), _clean_text("DummyClassifier")),
        ("leader_confusion", "Figure 7. Confusion matrix for the primary ROC leader." if lang == "en" else ("Figura 7. Matriz de confusión para el líder principal por ROC." if lang == "es" else "Şekil 7. Birincil ROC lideri için karmaşıklık matrisi."), _clean_text(evaluation.get("primary_metric_leader") or detail.get("primary_metric_leader") or "")),
        ("threshold_confusion", "Figure 8. Confusion matrix for the best thresholded classifier." if lang == "en" else ("Figura 8. Matriz de confusión para el mejor clasificador por umbral." if lang == "es" else "Şekil 8. En iyi eşiklenmiş sınıflandırıcı için karmaşıklık matrisi."), _clean_text(evaluation.get("best_thresholded_classifier") or "")),
    ]
    seen_confusion_models: set[str] = set()
    for chart_key, caption, model_name in confusion_targets:
        if not model_name or model_name in seen_confusion_models:
            continue
        seen_confusion_models.add(model_name)
        _add_picture_with_caption(doc, charts.get(chart_key, Path("__missing__")), caption, width=3.7)

    _add_heading(doc, _copy(lang, "roc_analysis"), 1)
    _add_picture_with_caption(doc, charts.get("roc_curves", Path("__missing__")), "Figure 9. ROC curves for score-capable stored models." if lang == "en" else ("Figura 9. Curvas ROC para los modelos almacenados capaces de producir puntuaciones." if lang == "es" else "Şekil 9. Skor üretebilen saklanan modeller için ROC eğrileri."), width=6.4)
    _add_paragraph(doc, _narrative_robust_winner(detail, run_summary, lang))

    _add_heading(doc, _copy(lang, "pr_analysis"), 1)
    _add_picture_with_caption(doc, charts.get("pr_curves", Path("__missing__")), "Figure 10. Precision-recall curves for the same stored holdout predictions." if lang == "en" else ("Figura 10. Curvas precision-recall para las mismas predicciones holdout almacenadas." if lang == "es" else "Şekil 10. Aynı saklanan holdout tahminleri için precision-recall eğrileri."), width=6.4)

    _add_heading(doc, _copy(lang, "calibration_analysis"), 1)
    _add_picture_with_caption(doc, charts.get("calibration_curves", Path("__missing__")), "Figure 11. Calibration curves derived from stored probabilities." if lang == "en" else ("Figura 11. Curvas de calibración derivadas de probabilidades almacenadas." if lang == "es" else "Şekil 11. Saklanan olasılıklardan türetilen kalibrasyon eğrileri."), width=6.4)
    _add_picture_with_caption(doc, charts.get("probability_distribution", Path("__missing__")), "Figure 12. Predicted-probability distributions for the stored leader, threshold leader, and baseline." if lang == "en" else ("Figura 12. Distribuciones de probabilidad predicha para el líder almacenado, el líder por umbral y la línea base." if lang == "es" else "Şekil 12. Saklanan lider, eşik lideri ve temel model için tahmin edilen olasılık dağılımları."), width=6.4)

    _add_heading(doc, _copy(lang, "error_analysis"), 1)
    _add_bullets(
        doc,
        [
            "False positives and false negatives can be inspected only through the stored anonymized holdout predictions; no raw user identifiers are exposed." if lang == "en" else ("Los falsos positivos y falsos negativos solo pueden inspeccionarse mediante las predicciones holdout anonimizadas almacenadas; no se exponen identificadores crudos de usuario." if lang == "es" else "Yanlış pozitifler ve yanlış negatifler yalnızca saklanan anonimleştirilmiş holdout tahminleri üzerinden incelenebilir; ham kullanıcı kimlikleri açığa çıkarılmaz."),
            "Subgroup sample sizes are too small for strong technical claims by topic, student-history bucket, or resource type, so subgroup interpretation should remain descriptive only." if lang == "en" else ("Los tamaños muestrales por subgrupo son demasiado pequeños para afirmaciones técnicas sólidas por tema, historial del estudiante o tipo de recurso, por lo que la interpretación debe seguir siendo descriptiva." if lang == "es" else "Alt grup örneklem boyutları; konu, öğrenci geçmişi kovası veya kaynak türü bazında güçlü teknik iddialar için çok küçüktür; bu nedenle yorum yalnızca betimleyici kalmalıdır."),
            "The confusion matrices show that threshold choice changes the balance between misses and false alarms more than it changes the overall conclusion." if lang == "en" else ("Las matrices de confusión muestran que la elección del umbral cambia más el equilibrio entre omisiones y falsas alarmas que la conclusión general." if lang == "es" else "Karmaşıklık matrisleri, eşik seçiminin genel sonucu değiştirmekten çok kaçırmalar ile yanlış alarmlar arasındaki dengeyi değiştirdiğini gösterir."),
        ],
    )

    _add_heading(doc, _copy(lang, "uncertainty"), 1)
    _add_bullets(
        doc,
        [
            "Confidence intervals are read from the stored model comparison CSV." if lang == "en" else ("Los intervalos de confianza se leen del CSV almacenado de comparación de modelos." if lang == "es" else "Güven aralıkları saklanan model karşılaştırma CSV dosyasından okunur."),
            "Small holdout size and single-teacher coverage mean all uncertainty intervals should be interpreted conservatively." if lang == "en" else ("El tamaño pequeño del holdout y la cobertura de un solo docente implican que todos los intervalos de incertidumbre deben interpretarse con prudencia." if lang == "es" else "Küçük holdout boyutu ve tek öğretmen kapsamı, tüm belirsizlik aralıklarının temkinli yorumlanması gerektiği anlamına gelir."),
            (f"Stored overall verdict: {get_run_status_display(str(review.get('final_verdict') or detail.get('run_status') or ''), lang=lang)}." if lang == "en" else (f"Veredicto general almacenado: {get_run_status_display(str(review.get('final_verdict') or detail.get('run_status') or ''), lang=lang)}." if lang == "es" else f"Saklanan genel hüküm: {get_run_status_display(str(review.get('final_verdict') or detail.get('run_status') or ''), lang=lang)}.")),
        ],
    )

    _add_heading(doc, _copy(lang, "runtime"), 1)
    _add_paragraph(doc, "Training and inference durations are reported directly from the validated model comparison artifact and shown in Figure 5." if lang == "en" else ("Las duraciones de entrenamiento e inferencia se reportan directamente desde el artefacto validado de comparación de modelos y se muestran en la Figura 5." if lang == "es" else "Eğitim ve çıkarım süreleri doğrudan doğrulanmış model karşılaştırma artefaktından raporlanır ve Şekil 5'te gösterilir."))

    _add_heading(doc, _copy(lang, "integrity"), 1)
    _add_bullets(
        doc,
        [
            _copy(lang, "technical_conclusion"),
            _translate_known_evidence_text(detail.get("validation_notes") or "", lang),
            "All intended models executed successfully in the validated run." if lang == "en" else ("Todos los modelos previstos se ejecutaron con éxito en la ejecución validada." if lang == "es" else "Planlanan tüm modeller doğrulanmış çalışmada başarıyla çalıştı."),
            "Artifact consistency checks confirmed shared run ID and data fingerprint across stored outputs." if lang == "en" else ("Las comprobaciones de consistencia de artefactos confirmaron ID de ejecución y huella de datos compartidos entre las salidas almacenadas." if lang == "es" else "Artefakt tutarlılık kontrolleri, saklanan çıktılar arasında ortak çalışma kimliği ve veri parmak izi olduğunu doğruladı."),
        ]
        + [_translate_known_evidence_text(item, lang) for item in list((review.get("label_reconciliation") or {}).get("limitations") or [])],
    )

    _add_heading(doc, _copy(lang, "conclusions"), 1)
    _add_note_box(
        doc,
        _copy(lang, "section_note"),
        str(ai_narrative.get("conclusion_paragraph") or _narrative_robust_winner(detail, run_summary, lang)),
    )

    _add_heading(doc, _copy(lang, "reproducibility"), 1)
    _add_bullets(
        doc,
        [
            (f"Run ID: {run_id}" if lang == "en" else (f"ID de ejecución: {run_id}" if lang == "es" else f"Çalışma kimliği: {run_id}")),
            (f"Dataset fingerprint: {detail.get('dataset_fingerprint') or 'n/a'}" if lang == "en" else (f"Huella del conjunto de datos: {detail.get('dataset_fingerprint') or 'n/a'}" if lang == "es" else f"Veri kümesi parmak izi: {detail.get('dataset_fingerprint') or 'n/a'}")),
            (f"Feature schema version: {_humanize_identifier(dataset_summary.get('feature_schema_version') or run_summary.get('feature_schema_version') or 'n/a')}" if lang == "en" else (f"Versión del esquema de variables: {_humanize_identifier(dataset_summary.get('feature_schema_version') or run_summary.get('feature_schema_version') or 'n/a')}" if lang == "es" else f"Özellik şeması sürümü: {_humanize_identifier(dataset_summary.get('feature_schema_version') or run_summary.get('feature_schema_version') or 'n/a')}")),
            "This report was generated from stored artifacts only; it does not recompute training metrics independently." if lang == "en" else ("Este informe se generó solo a partir de artefactos almacenados; no recompone ni recalcula métricas de entrenamiento de forma independiente." if lang == "es" else "Bu rapor yalnızca saklanan artefaktlardan üretildi; eğitim metriklerini bağımsız olarak yeniden hesaplamaz."),
        ],
    )

    _add_heading(doc, _copy(lang, "implementation"), 1)
    _add_note_box(
        doc,
        _copy(lang, "section_note"),
        str(
            ai_narrative.get("implementation_paragraph")
            or (
                "Current evidence supports continued supervised experimentation, but not a production change. Any operational change should wait for broader teacher coverage, stronger telemetry consistency, and another validated run."
                if lang == "en"
                else (
                    "La evidencia actual respalda seguir experimentando con modelos supervisados, pero no un cambio en producción. Cualquier cambio operativo debería esperar a una cobertura docente más amplia, mayor consistencia de telemetría y otra ejecución validada."
                    if lang == "es"
                    else "Mevcut kanıtlar denetimli deneylerin sürdürülmesini destekliyor, ancak üretimde bir değişikliği desteklemiyor. Operasyonel bir değişiklik için daha geniş öğretmen kapsamı, daha tutarlı telemetri ve yeni bir doğrulanmış çalışma beklenmelidir."
                )
            )
        ),
    )

    _add_heading(doc, _copy(lang, "limitations"), 1)
    limitation_rows = _unique_nonempty(
        list(ai_narrative.get("limitations") or [])
        + list(academic.get("limitations") or [])
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

    _add_heading(doc, "Meeting Notes and Decision Record" if lang == "en" else ("Notas de reunión y registro de decisión" if lang == "es" else "Toplantı notları ve karar kaydı"), 2)
    _add_table(doc, [_copy(lang, "meta_field"), _copy(lang, "meta_value")], _meeting_notes_rows(report_context, lang)[1:], [2.2, 4.5])

    if model_rows:
        _add_landscape_section(doc)
        _apply_page_furniture(doc, _copy(lang, "technical_report_name"), run_id, lang)
        _add_heading(doc, _phrase(lang, "full_model_comparison"), 2)
        for title, headers, rows, widths, numeric_cols in _model_metric_groups(model_rows, lang):
            _add_heading(doc, title, 3)
            _add_table(doc, headers, rows, widths, numeric_cols=numeric_cols, caption=_copy(lang, "caption_models"))

    report_dir = _report_dir(run_id, lang)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / _report_filename("technical_docx", run_id)
    doc.save(path)
    return {
        "ok": True,
        "path": str(path),
        "bytes": _verified_docx_bytes(path),
        "report_type": "technical_docx",
        "generation_mode": "ai" if bool(ai_narrative.get("_ai_used")) else "template",
        "provider": str(ai_narrative.get("_provider") or ""),
    }


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
    return {
        "ok": True,
        "path": str(target_path),
        "bytes": _verified_docx_bytes(target_path),
        "report_type": "experiment_docx",
        "generation_mode": str(technical.get("generation_mode") or "template"),
        "provider": str(technical.get("provider") or ""),
    }


def get_or_create_validated_report(run_id: str, report_type: str, language: str, *, force_regenerate: bool = False) -> dict[str, Any]:
    safe_type = _clean_text(report_type)
    safe_run_id = _clean_text(run_id)
    lang = _lang(language)
    if safe_type not in REPORT_TYPES:
        return {"ok": False, "message": t("admin_eic_report_generation_failed", lang=lang)}
    path = _report_dir(safe_run_id, lang) / _report_filename(safe_type, safe_run_id)
    if path.exists() and not force_regenerate:
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
            row["modified_at"] = _format_file_timestamp(path, lang) if path.exists() else ""
            try:
                row["modified_epoch"] = int(path.stat().st_mtime) if path.exists() else 0
            except Exception:
                row["modified_epoch"] = 0
        else:
            row["path"] = ""
            row["download_ready"] = False
            row["modified_at"] = ""
            row["modified_epoch"] = 0
    return base_rows
