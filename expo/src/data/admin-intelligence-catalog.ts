// Generated from Streamlit's reviewed EIC blueprint and translation catalogs.
export const ADMIN_INTELLIGENCE_CATALOG = [
  {
    "component_id": "teacher_recommendation_objective_selector",
    "component_type": "hybrid_intelligence",
    "operational_status": "live",
    "data_maturity": "collecting_data",
    "evidence_maturity": "limited",
    "translations": {
      "en": {
        "name": "Teacher Recommendation Objective Selector",
        "business_question": "Which pedagogical objective should the teacher tackle next?",
        "decision_supported": "Which student-topic card should rank highest in the teacher recommendation panel.",
        "production_use": "Ranks live teacher recommendation cards.",
        "limitation": "Uses handcrafted proxy targets from recommendation-event summaries.",
        "product_surface": "Teacher recommendations in Students workspace.",
        "educational_value": "Helps teachers prioritize the next topic or review action.",
        "outcome_metric": "Not measurable yet"
      },
      "es": {
        "name": "Selector de objetivo de recomendación docente",
        "business_question": "¿Qué objetivo pedagógico debería abordar el profesor a continuación?",
        "decision_supported": "Qué tarjeta estudiante-tema debería quedar más alta en el panel de recomendación docente.",
        "production_use": "Ordena las tarjetas de recomendación docente en vivo.",
        "limitation": "Usa objetivos proxy artesanales a partir de resúmenes de eventos de recomendación.",
        "product_surface": "Recomendaciones docentes en el espacio Students.",
        "educational_value": "Ayuda a los profesores a priorizar el siguiente tema o acción de repaso.",
        "outcome_metric": "Todavía no es medible"
      },
      "tr": {
        "name": "Öğretmen öneri hedef seçici",
        "business_question": "Öğretmen sırada hangi pedagojik hedefi ele almalı?",
        "decision_supported": "Öğretmen öneri panelinde hangi öğrenci-konu kartının en üstte yer alması gerektiği.",
        "production_use": "Canlı öğretmen öneri kartlarını sıralar.",
        "limitation": "Öneri olayı özetlerinden el yapımı vekil hedefler kullanır.",
        "product_surface": "Students çalışma alanındaki öğretmen önerileri.",
        "educational_value": "Öğretmenlerin bir sonraki konu veya tekrar eylemini önceliklendirmesine yardımcı olur.",
        "outcome_metric": "Henüz ölçülebilir değil"
      }
    }
  },
  {
    "component_id": "teacher_recommendation_resource_ranker",
    "component_type": "heuristic_ranker",
    "operational_status": "live",
    "data_maturity": "collecting_data",
    "evidence_maturity": "limited",
    "translations": {
      "en": {
        "name": "Teacher Recommendation Resource Ranker",
        "business_question": "Which supporting resource best fits the teacher recommendation item?",
        "decision_supported": "Which worksheet, exam, or video should support the recommended objective.",
        "production_use": "Ranks teacher resource options in live recommendations.",
        "limitation": "Training signal is a proxy and includes post-selection actions.",
        "product_surface": "Teacher recommendation resource picker.",
        "educational_value": "Improves the quality of supporting materials attached to teacher actions.",
        "outcome_metric": "Not measurable yet"
      },
      "es": {
        "name": "Clasificador de recursos para recomendación docente",
        "business_question": "¿Qué recurso de apoyo encaja mejor con la recomendación docente?",
        "decision_supported": "Qué ficha, examen o video debería apoyar el objetivo recomendado.",
        "production_use": "Ordena opciones de recursos docentes en recomendaciones en vivo.",
        "limitation": "La señal de entrenamiento es proxy e incluye acciones posteriores a la selección.",
        "product_surface": "Selector de recursos para recomendación docente.",
        "educational_value": "Mejora la calidad de los materiales de apoyo ligados a acciones docentes.",
        "outcome_metric": "Todavía no es medible"
      },
      "tr": {
        "name": "Öğretmen öneri kaynak sıralayıcı",
        "business_question": "Hangi destek kaynağı öğretmen öneri maddesine en iyi uyar?",
        "decision_supported": "Önerilen hedefi hangi çalışma kağıdı, sınav veya videonun desteklemesi gerektiği.",
        "production_use": "Canlı önerilerde öğretmen kaynak seçeneklerini sıralar.",
        "limitation": "Eğitim sinyali vekildir ve seçim sonrası eylemleri içerir.",
        "product_surface": "Öğretmen öneri kaynak seçici.",
        "educational_value": "Öğretmen eylemlerine eklenen destek materyallerinin kalitesini artırır.",
        "outcome_metric": "Henüz ölçülebilir değil"
      }
    }
  },
  {
    "component_id": "teacher_material_feed_ranker",
    "component_type": "heuristic_ranker",
    "operational_status": "production",
    "data_maturity": "healthy",
    "evidence_maturity": "direct_observed_data",
    "translations": {
      "en": {
        "name": "Teacher Material Feed Ranker",
        "business_question": "Which materials should teachers see first in their feed?",
        "decision_supported": "How teacher home and explore materials are ordered.",
        "production_use": "Orders teacher material feed cards today.",
        "limitation": "No tenant identifier beyond teacher_id, so cross-teacher aggregation needs care.",
        "product_surface": "Teacher Home feed.",
        "educational_value": "Surfaces reusable teaching materials efficiently.",
        "outcome_metric": "Teacher material opens are measurable."
      },
      "es": {
        "name": "Clasificador del feed de materiales docentes",
        "business_question": "¿Qué materiales deberían ver primero los profesores en su feed?",
        "decision_supported": "Cómo se ordenan los materiales del home y explore docente.",
        "production_use": "Ordena hoy las tarjetas del feed de materiales docentes.",
        "limitation": "No hay identificador de tenant más allá de teacher_id, así que la agregación entre profesores requiere cuidado.",
        "product_surface": "Feed de Teacher Home.",
        "educational_value": "Hace más eficiente la visibilidad de materiales reutilizables.",
        "outcome_metric": "Las aperturas de materiales docentes sí son medibles"
      },
      "tr": {
        "name": "Öğretmen materyal akışı sıralayıcı",
        "business_question": "Öğretmenler akışlarında önce hangi materyalleri görmeli?",
        "decision_supported": "Öğretmen ana sayfası ve keşfet materyallerinin nasıl sıralandığı.",
        "production_use": "Bugün öğretmen materyal akışı kartlarını sıralar.",
        "limitation": "teacher_id dışında tenant tanımlayıcısı yok, bu yüzden öğretmenler arası toplulaştırma dikkat ister.",
        "product_surface": "Teacher Home akışı.",
        "educational_value": "Yeniden kullanılabilir öğretim materyallerini verimli şekilde öne çıkarır.",
        "outcome_metric": "Öğretmen materyal açılışları ölçülebilir"
      }
    }
  },
  {
    "component_id": "student_recommendation_ranker",
    "component_type": "hybrid_intelligence",
    "operational_status": "live",
    "data_maturity": "collecting_labels",
    "evidence_maturity": "limited",
    "translations": {
      "en": {
        "name": "Student Recommendation Ranker",
        "business_question": "Which practice resource should the learner see next?",
        "decision_supported": "What optional practice recommendation is shown to the student.",
        "production_use": "Ranks optional student recommendations in production.",
        "limitation": "Impression logging is inconsistent across student surfaces.",
        "product_surface": "Student Practice and Student Home.",
        "educational_value": "Personalizes what the learner should practice next.",
        "outcome_metric": "Not measurable yet"
      },
      "es": {
        "name": "Clasificador de recomendaciones para estudiantes",
        "business_question": "¿Qué recurso de práctica debería ver después el estudiante?",
        "decision_supported": "Qué recomendación opcional de práctica se muestra al estudiante.",
        "production_use": "Ordena recomendaciones opcionales de estudiantes en producción.",
        "limitation": "El registro de impresiones es inconsistente entre superficies del estudiante.",
        "product_surface": "Student Practice y Student Home.",
        "educational_value": "Personaliza lo que el estudiante debería practicar a continuación.",
        "outcome_metric": "Todavía no es medible"
      },
      "tr": {
        "name": "Öğrenci öneri sıralayıcı",
        "business_question": "Öğrenciye sıradaki hangi çalışma kaynağı gösterilmeli?",
        "decision_supported": "Öğrenciye hangi isteğe bağlı çalışma önerisinin gösterildiği.",
        "production_use": "Üretimde isteğe bağlı öğrenci önerilerini sıralar.",
        "limitation": "Gösterim kaydı öğrenci yüzeyleri arasında tutarsız.",
        "product_surface": "Student Practice ve Student Home.",
        "educational_value": "Öğrencinin sırada ne çalışması gerektiğini kişiselleştirir.",
        "outcome_metric": "Henüz ölçülebilir değil"
      }
    }
  },
  {
    "component_id": "student_recommendation_acceptance_blend_model",
    "component_type": "statistical_estimator",
    "operational_status": "experimental",
    "data_maturity": "collecting_data",
    "evidence_maturity": "proxy_only",
    "translations": {
      "en": {
        "name": "Student Recommendation Acceptance / Blend Model",
        "business_question": "How much should the live student ranker trust the learned score?",
        "decision_supported": "The blend between heuristic rank score and learned proxy score.",
        "production_use": "Contributes an ml_score and blend weight to the student ranker.",
        "limitation": "Uses handcrafted proxy labels, not real impression-to-open outcomes.",
        "product_surface": "Student recommendation scoring internals.",
        "educational_value": "Attempts to personalize optional practice ranking.",
        "outcome_metric": "Proxy-only evaluation"
      },
      "es": {
        "name": "Modelo de aceptación / mezcla de recomendaciones del estudiante",
        "business_question": "¿Cuánto debería confiar el ranker estudiantil en vivo en la puntuación aprendida?",
        "decision_supported": "La mezcla entre la puntuación heurística y la puntuación proxy aprendida.",
        "production_use": "Aporta un ml_score y un peso de mezcla al ranker del estudiante.",
        "limitation": "Usa etiquetas proxy artesanales, no resultados reales de impresión a apertura.",
        "product_surface": "Internos de puntuación de recomendación estudiantil.",
        "educational_value": "Intenta personalizar el orden de práctica opcional.",
        "outcome_metric": "Evaluación solo proxy"
      },
      "tr": {
        "name": "Öğrenci öneri kabul / harman modeli",
        "business_question": "Canlı öğrenci sıralayıcısı öğrenilmiş puana ne kadar güvenmeli?",
        "decision_supported": "Sezgisel sıra puanı ile öğrenilmiş vekil puan arasındaki karışım.",
        "production_use": "Öğrenci sıralayıcısına ml_score ve karışım ağırlığı katkısı verir.",
        "limitation": "Gerçek gösterim-açılma sonuçları yerine elde hazırlanmış vekil etiketler kullanır.",
        "product_surface": "Öğrenci öneri puanlaması iç yapısı.",
        "educational_value": "İsteğe bağlı çalışma sıralamasını kişiselleştirmeyi dener.",
        "outcome_metric": "Yalnızca proxy değerlendirme"
      }
    }
  },
  {
    "component_id": "explicit_topic_resource_matching",
    "component_type": "statistical_estimator",
    "operational_status": "production",
    "data_maturity": "partial",
    "evidence_maturity": "feature_source",
    "translations": {
      "en": {
        "name": "Explicit Topic-Resource Matching",
        "business_question": "How historically aligned is a resource with a topic?",
        "decision_supported": "Whether a resource should receive topic-match support in ranking.",
        "production_use": "Acts as a feature source for teacher and student ranking.",
        "limitation": "Sparse assignment topic coverage limits present-day support.",
        "product_surface": "Teacher and student resource ranking.",
        "educational_value": "Improves topic fit between content and learning needs.",
        "outcome_metric": "Not measurable yet"
      },
      "es": {
        "name": "Emparejamiento explícito tema-recurso",
        "business_question": "¿Qué tan alineado está históricamente un recurso con un tema?",
        "decision_supported": "Si un recurso debería recibir apoyo de coincidencia temática en el ranking.",
        "production_use": "Actúa como fuente de variables para ranking docente y estudiantil.",
        "limitation": "La cobertura escasa de temas en asignaciones limita el apoyo actual.",
        "product_surface": "Ranking de recursos de profesores y estudiantes.",
        "educational_value": "Mejora el ajuste entre contenido y necesidad de aprendizaje.",
        "outcome_metric": "Todavía no es medible"
      },
      "tr": {
        "name": "Açık konu-kaynak eşleştirmesi",
        "business_question": "Bir kaynak tarihsel olarak bir konuyla ne kadar uyumlu?",
        "decision_supported": "Bir kaynağın sıralamada konu eşleşmesi desteği alıp almaması.",
        "production_use": "Öğretmen ve öğrenci sıralaması için özellik kaynağı olarak çalışır.",
        "limitation": "Seyrek ödev konu kapsamı bugünkü desteği sınırlıyor.",
        "product_surface": "Öğretmen ve öğrenci kaynak sıralaması.",
        "educational_value": "İçerik ile öğrenme ihtiyacı arasındaki konu uyumunu geliştirir.",
        "outcome_metric": "Henüz ölçülebilir değil"
      }
    }
  },
  {
    "component_id": "practice_mastery_aggregator",
    "component_type": "deterministic_workflow",
    "operational_status": "production",
    "data_maturity": "healthy",
    "evidence_maturity": "direct_observed_data",
    "translations": {
      "en": {
        "name": "Practice Mastery Aggregator",
        "business_question": "What has the student practised and mastered?",
        "decision_supported": "How practice history is summarized for progress and recommendations.",
        "production_use": "Powering progress summaries and feature generation today.",
        "limitation": "None material to supervised readiness; it is deterministic by design.",
        "product_surface": "Practice progress and downstream recommendations.",
        "educational_value": "Provides a reliable mastery picture from observed student practice.",
        "outcome_metric": "Direct observed data"
      },
      "es": {
        "name": "Agregador de dominio de práctica",
        "business_question": "¿Qué ha practicado y dominado el estudiante?",
        "decision_supported": "Cómo se resume el historial de práctica para progreso y recomendaciones.",
        "production_use": "Impulsa hoy resúmenes de progreso y generación de variables.",
        "limitation": "No hay limitación material para preparación supervisada; es determinista por diseño.",
        "product_surface": "Progreso de práctica y recomendaciones derivadas.",
        "educational_value": "Aporta una imagen fiable del dominio a partir de la práctica observada.",
        "outcome_metric": "Datos observados directos"
      },
      "tr": {
        "name": "Alıştırma ustalık toplayıcısı",
        "business_question": "Öğrenci neyi çalıştı ve hangi alanlarda ustalaştı?",
        "decision_supported": "Çalışma geçmişinin ilerleme ve öneriler için nasıl özetlendiği.",
        "production_use": "Bugün ilerleme özetlerini ve özellik üretimini besliyor.",
        "limitation": "Denetimli hazır oluşla ilgili maddi bir sınırlama yok; tasarım gereği deterministiktir.",
        "product_surface": "Çalışma ilerlemesi ve sonraki öneriler.",
        "educational_value": "Gözlemlenen öğrenci çalışmasından güvenilir bir ustalık görünümü sunar.",
        "outcome_metric": "Doğrudan gözlemlenen veri"
      }
    }
  },
  {
    "component_id": "review_synchronization_loop",
    "component_type": "deterministic_workflow",
    "operational_status": "production",
    "data_maturity": "healthy",
    "evidence_maturity": "direct_observed_data",
    "translations": {
      "en": {
        "name": "Review Synchronization Loop",
        "business_question": "How should review corrections propagate back into practice and assignments?",
        "decision_supported": "How corrected answers update downstream student records.",
        "production_use": "Synchronizes review outcomes across practice and assignment records.",
        "limitation": "Not a supervised-learning candidate.",
        "product_surface": "Teacher review and practice correction workflows.",
        "educational_value": "Keeps progress and review outcomes consistent for the learner.",
        "outcome_metric": "Review closure is measurable"
      },
      "es": {
        "name": "Bucle de sincronización de revisiones",
        "business_question": "¿Cómo deberían propagarse las correcciones de revisión hacia práctica y asignaciones?",
        "decision_supported": "Cómo las respuestas corregidas actualizan registros posteriores del estudiante.",
        "production_use": "Sincroniza resultados de revisión entre práctica y asignaciones.",
        "limitation": "No es candidato para aprendizaje supervisado.",
        "product_surface": "Flujos de revisión docente y corrección de práctica.",
        "educational_value": "Mantiene consistentes el progreso y los resultados de revisión.",
        "outcome_metric": "El cierre de revisión es medible"
      },
      "tr": {
        "name": "İnceleme senkronizasyon döngüsü",
        "business_question": "Düzeltmeler çalışmaya ve ödevlere nasıl geri yayılmalı?",
        "decision_supported": "Düzeltilmiş cevapların aşağı akıştaki öğrenci kayıtlarını nasıl güncellediği.",
        "production_use": "Değerlendirme sonuçlarını çalışma ve ödev kayıtları arasında senkronize eder.",
        "limitation": "Denetimli öğrenme adayı değildir.",
        "product_surface": "Öğretmen değerlendirme ve çalışma düzeltme akışları.",
        "educational_value": "Öğrenci için ilerleme ve değerlendirme sonuçlarını tutarlı tutar.",
        "outcome_metric": "Gözden geçirme kapanışı ölçülebilir"
      }
    }
  },
  {
    "component_id": "material_reuse_similarity_retriever",
    "component_type": "retrieval_system",
    "operational_status": "production",
    "data_maturity": "healthy",
    "evidence_maturity": "direct_observed_data",
    "translations": {
      "en": {
        "name": "Material Reuse Similarity Retriever",
        "business_question": "Which previously created material can be reused for a similar need?",
        "decision_supported": "Whether to suggest an existing material instead of creating a new one.",
        "production_use": "Retrieves reusable material suggestions for teachers.",
        "limitation": "Should remain retrieval-oriented rather than framed as supervised ML.",
        "product_surface": "Material recommendation and reuse flows.",
        "educational_value": "Saves teacher planning time through reuse.",
        "outcome_metric": "Reuse opportunities observed"
      },
      "es": {
        "name": "Recuperador de similitud para reutilización de materiales",
        "business_question": "¿Qué material previamente creado puede reutilizarse para una necesidad similar?",
        "decision_supported": "Si conviene sugerir un material existente en lugar de crear uno nuevo.",
        "production_use": "Recupera sugerencias de materiales reutilizables para profesores.",
        "limitation": "Debería mantenerse como sistema de recuperación, no como ML supervisado.",
        "product_surface": "Flujos de recomendación y reutilización de materiales.",
        "educational_value": "Ahorra tiempo de planificación docente mediante reutilización.",
        "outcome_metric": "Oportunidades de reutilización observadas"
      },
      "tr": {
        "name": "Materyal yeniden kullanım benzerlik getiricisi",
        "business_question": "Daha önce oluşturulan hangi materyal benzer bir ihtiyaç için yeniden kullanılabilir?",
        "decision_supported": "Yeni bir içerik oluşturmak yerine mevcut bir materyalin önerilip önerilmemesi.",
        "production_use": "Öğretmenler için yeniden kullanılabilir materyal önerileri getirir.",
        "limitation": "Denetimli ML olarak değil, erişim odaklı bir yapı olarak kalmalıdır.",
        "product_surface": "Materyal öneri ve yeniden kullanım akışları.",
        "educational_value": "Yeniden kullanım yoluyla öğretmenin planlama süresini azaltır.",
        "outcome_metric": "Gözlemlenen yeniden kullanım fırsatları"
      }
    }
  },
  {
    "component_id": "recommendation_event_feedback_loop",
    "component_type": "deterministic_workflow",
    "operational_status": "experimental",
    "data_maturity": "partial",
    "evidence_maturity": "limited",
    "translations": {
      "en": {
        "name": "Recommendation Event Feedback Loop",
        "business_question": "Is recommendation telemetry capturing enough real feedback to improve the system?",
        "decision_supported": "Whether Classio has enough recommendation evidence to train or validate better rankers.",
        "production_use": "Collects recommendation events for analysis.",
        "limitation": "Sparse exposure logging and duplicate-risk ambiguity remain.",
        "product_surface": "Recommendation telemetry layer.",
        "educational_value": "Creates the evidence base needed for future personalization.",
        "outcome_metric": "Not measurable yet"
      },
      "es": {
        "name": "Bucle de retroalimentación de eventos de recomendación",
        "business_question": "¿La telemetría de recomendaciones está capturando suficiente feedback real para mejorar el sistema?",
        "decision_supported": "Si Classio ya tiene evidencia suficiente para entrenar o validar mejores rankers.",
        "production_use": "Recoge eventos de recomendación para análisis.",
        "limitation": "Persisten el registro escaso de exposiciones y la ambigüedad por duplicados.",
        "product_surface": "Capa de telemetría de recomendaciones.",
        "educational_value": "Construye la base de evidencia necesaria para la personalización futura.",
        "outcome_metric": "Todavía no es medible"
      },
      "tr": {
        "name": "Öneri olay geri bildirim döngüsü",
        "business_question": "Öneri telemetrisi sistemi geliştirmek için yeterli gerçek geri bildirim topluyor mu?",
        "decision_supported": "Classio’nun daha iyi sıralayıcılar eğitmek veya doğrulamak için yeterli öneri kanıtına sahip olup olmadığı.",
        "production_use": "Analiz için öneri olaylarını toplar.",
        "limitation": "Seyrek gösterim kaydı ve yinelenen risk belirsizliği sürüyor.",
        "product_surface": "Öneri telemetrisi katmanı.",
        "educational_value": "Gelecekteki kişiselleştirme için gereken kanıt tabanını oluşturur.",
        "outcome_metric": "Henüz ölçülebilir değil"
      }
    }
  },
  {
    "component_id": "assigned_resource_open_within_7d",
    "component_type": "supervised_experiment",
    "operational_status": "offline_evaluation",
    "data_maturity": "validated_evidence_ready",
    "evidence_maturity": "exploratory",
    "translations": {
      "en": {
        "name": "Assigned Resource Open Within 7 Days",
        "business_question": "Can Classio predict whether a student will open an assigned resource within seven days?",
        "decision_supported": "Whether supervised prediction is credible enough to compare against current heuristics.",
        "production_use": "Offline validated evaluation only. No live model deployment.",
        "limitation": "Current mature label set is dominated by one teacher.",
        "product_surface": "Developer Workspace and Intelligence Center evidence views.",
        "educational_value": "Could eventually improve assignment follow-through decisions.",
        "outcome_metric": "Seven-day assignment open label"
      },
      "es": {
        "name": "Apertura de recurso asignado dentro de 7 días",
        "business_question": "¿Puede Classio predecir si un estudiante abrirá un recurso asignado dentro de siete días?",
        "decision_supported": "Si la predicción supervisada es lo bastante creíble para compararse con la heurística actual.",
        "production_use": "Solo evaluación validada offline. Sin despliegue de modelos en vivo.",
        "limitation": "El conjunto de etiquetas maduras actual está dominado por un solo profesor.",
        "product_surface": "Vistas de evidencia del Espacio de Trabajo del Desarrollador y del Centro de Inteligencia.",
        "educational_value": "Podría mejorar decisiones futuras sobre seguimiento de tareas.",
        "outcome_metric": "Etiqueta de apertura de asignación a siete días"
      },
      "tr": {
        "name": "Atanan kaynağın 7 gün içinde açılması",
        "business_question": "Classio, bir öğrencinin atanan kaynağı yedi gün içinde açıp açmayacağını tahmin edebilir mi?",
        "decision_supported": "Denetimli tahminin mevcut sezgilerle karşılaştırılacak kadar güvenilir olup olmadığı.",
        "production_use": "Yalnızca çevrimdışı doğrulanmış değerlendirme. Canlı model dağıtımı yok.",
        "limitation": "Mevcut olgun etiket kümesi büyük ölçüde tek bir öğretmene dayanıyor.",
        "product_surface": "Developer Workspace ve Intelligence Center kanıt görünümleri.",
        "educational_value": "Zamanla ödev takibi kararlarını iyileştirebilir.",
        "outcome_metric": "Yedi günlük ödev açılma etiketi"
      }
    }
  }
] as const;
