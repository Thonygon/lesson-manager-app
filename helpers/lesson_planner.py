import streamlit as st
import json, datetime, os, re
from typing import Optional
from openai import OpenAI
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local, get_app_tz
from core.database import get_sb, load_table, load_students, register_cache
from translations import I18N

# 07.1A) QUICK LESSON PLANNER HELPERS
# =========================

QUICK_SUBJECTS = [
    "english",
    "spanish",
    "mathematics",
    "science",
    "music",
    "study_skills",
    "other",
]

SUBJECT_ENGINE_MAP = {
    "english": "language",
    "spanish": "language",
    "mathematics": "math",
    "science": "science",
    "music": "music",
    "study_skills": "study_skills",
}

LEARNER_STAGES = [
    "early_primary",
    "upper_primary",
    "lower_secondary",
    "upper_secondary",
    "adult_stage",
]

LANGUAGE_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
ACADEMIC_BANDS = ["beginner_band", "intermediate_band", "advanced_band"]

LESSON_PURPOSES = [
    "introduce_concept",
    "practice_skill",
    "review_topic",
    "diagnose_difficulty",
    "discussion_exploration",
]


def subject_label(subject_key: str) -> str:
    if str(subject_key).strip().lower() == "other":
        return t("explore_other")
    return t(f"subject_{subject_key}")


def get_subject_engine(subject: str) -> str:
    s = str(subject or "").strip().lower()
    return SUBJECT_ENGINE_MAP.get(s, "general")


def get_plan_language() -> str:
    lang = str(st.session_state.get("ui_lang", "en")).strip().lower()
    return lang if lang in {"en", "es", "tr"} else "en"


def get_student_material_language(subject: str) -> str:
    s = str(subject or "").strip().lower()
    if s == "english":
        return "en"
    if s == "spanish":
        return "es"
    return get_plan_language()


def qlp_txt(en: str, es: str, tr: str) -> str:
    lang = get_plan_language()
    if lang == "es":
        return es
    if lang == "tr":
        return tr
    return en


def get_level_options(subject: str) -> list[str]:
    return LANGUAGE_LEVELS if get_subject_engine(subject) == "language" else ACADEMIC_BANDS


def recommend_default_level(subject: str, learner_stage: str) -> str:
    if get_subject_engine(subject) == "language":
        defaults = {
            "early_primary": "A1",
            "upper_primary": "A1",
            "lower_secondary": "A2",
            "upper_secondary": "B1",
            "adult_stage": "B1",
        }
        return defaults.get(learner_stage, "A1")

    defaults = {
        "early_primary": "beginner_band",
        "upper_primary": "beginner_band",
        "lower_secondary": "intermediate_band",
        "upper_secondary": "intermediate_band",
        "adult_stage": "advanced_band",
    }
    return defaults.get(learner_stage, "beginner_band")


def _stage_label(stage: str) -> str:
    return t(stage)


def _level_label(level: str) -> str:
    return level if level in LANGUAGE_LEVELS else t(level)


def _purpose_label(purpose: str) -> str:
    return t(purpose)


def _topic_clean(topic: str) -> str:
    return _clean_display_text(topic)


def _clean_display_text(text: str) -> str:
    s = str(text or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([.,!?;:])", r"\1", s)
    s = re.sub(r"\s*-\s*", " - ", s)
    s = re.sub(r"\s*/\s*", " / ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s:
        s = s[0].upper() + s[1:]
    return s


def _capitalize_topic(topic: str) -> str:
    s = _topic_clean(topic)
    return s[:1].upper() + s[1:] if s else ""


def _teacher_move_block(engine: str, purpose: str) -> list[str]:
    if engine == "language":
        base = [
            qlp_txt(
                "Model one answer before asking the student to answer alone.",
                "Modela una respuesta antes de pedirle al estudiante que responda solo.",
                "Öğrenciden tek başına cevap vermesini istemeden önce bir örnek cevap modelleyin.",
            ),
            qlp_txt(
                "If the student struggles, give a sentence starter instead of the full answer.",
                "Si el estudiante tiene dificultad, dale un inicio de oración en vez de la respuesta completa.",
                "Öğrenci zorlanırsa tam cevabı vermek yerine bir cümle başlangıcı verin.",
            ),
            qlp_txt(
                "Correct only the error that blocks meaning first.",
                "Corrige primero solo el error que bloquea el significado.",
                "Önce yalnızca anlamı engelleyen hatayı düzeltin.",
            ),
        ]
    elif engine == "math":
        base = [
            qlp_txt(
                "Ask the student to explain each step aloud.",
                "Pídele al estudiante que explique cada paso en voz alta.",
                "Öğrenciden her adımı yüksek sesle açıklamasını isteyin.",
            ),
            qlp_txt(
                "If the student gets stuck, reveal only the next step.",
                "Si el estudiante se bloquea, muestra solo el siguiente paso.",
                "Öğrenci takılırsa yalnızca bir sonraki adımı gösterin.",
            ),
            qlp_txt(
                "Check whether the mistake is conceptual or just arithmetic.",
                "Comprueba si el error es conceptual o solo aritmético.",
                "Hatanın kavramsal mı yoksa yalnızca işlem hatası mı olduğunu kontrol edin.",
            ),
        ]
    elif engine == "science":
        base = [
            qlp_txt(
                "Ask for a prediction before explaining the concept.",
                "Pide una predicción antes de explicar el concepto.",
                "Kavramı açıklamadan önce öğrenciden bir tahmin isteyin.",
            ),
            qlp_txt(
                "Use one real-life example before giving the formal explanation.",
                "Usa un ejemplo de la vida real antes de dar la explicación formal.",
                "Resmî açıklamayı vermeden önce günlük hayattan bir örnek kullanın.",
            ),
            qlp_txt(
                "Rebuild understanding from the phenomenon, not from memorized definitions.",
                "Reconstruye la comprensión desde el fenómeno, no desde definiciones memorizadas.",
                "Anlayışı ezberlenmiş tanımlardan değil, gözlenen olgudan başlayarak kurun.",
            ),
        ]
    elif engine == "music":
        base = [
            qlp_txt(
                "Demonstrate first, then ask for imitation.",
                "Demuestra primero y luego pide imitación.",
                "Önce gösterin, sonra taklit etmesini isteyin.",
            ),
            qlp_txt(
                "Correct one thing at a time.",
                "Corrige una cosa a la vez.",
                "Her seferinde yalnızca bir şeyi düzeltin.",
            ),
            qlp_txt(
                "Use short repetition cycles instead of long explanations.",
                "Usa ciclos cortos de repetición en lugar de explicaciones largas.",
                "Uzun açıklamalar yerine kısa tekrar döngüleri kullanın.",
            ),
        ]
    else:
        base = [
            qlp_txt(
                "Model the strategy with a real example.",
                "Modela la estrategia con un ejemplo real.",
                "Stratejiyi gerçek bir örnekle modelleyin.",
            ),
            qlp_txt(
                "Ask the student where they could use this this week.",
                "Pregúntale al estudiante dónde podría usar esto esta semana.",
                "Öğrenciye bunu bu hafta nerede kullanabileceğini sorun.",
            ),
            qlp_txt(
                "Focus on transfer, not just explanation.",
                "Enfócate en la transferencia, no solo en la explicación.",
                "Sadece açıklamaya değil, transfer etmeye de odaklanın.",
            ),
        ]

    if purpose == "diagnose_difficulty":
        base.append(
            qlp_txt(
                "Delay correction briefly so you can see exactly where the confusion starts.",
                "Retrasa un poco la corrección para ver exactamente dónde empieza la confusión.",
                "Karışıklığın tam olarak nerede başladığını görmek için düzeltmeyi kısa bir süre geciktirin.",
            )
        )

    return base


# -------------------------
# LANGUAGE CONTENT BANK
# -------------------------
LANGUAGE_CONTENT_BANK = {
    "travel": {
        "en": {
            "A1_A2": {
                "target_vocabulary": ["travel", "trip", "ticket", "hotel", "visit"],
                "warm_up": [
                    "Have you ever traveled to another city or country?",
                    "What do people usually need before a trip?",
                    "What places do you like to visit?"
                ],
                "reading_passage": (
                    "Marta is planning a trip to Ankara for the weekend. She wants to travel by bus because it is cheaper than the plane. "
                    "She already has a small bag, comfortable shoes, and a list of places to visit. On Saturday morning, she wants to see the old city, "
                    "eat local food, and buy a gift for her family. She is excited because she does not travel very often."
                ),
                "listening_script": (
                    "Good morning, everyone. Today we are talking about travel plans. Marta is going to Ankara this weekend. "
                    "She is travelling by bus and she wants to visit the old city, try local food, and buy a souvenir. "
                    "She feels excited because she does not travel very often."
                ),
                "pre_task_questions": [
                    "What do people usually prepare before a trip?",
                    "What words do you expect to hear in a text about travel?"
                ],
                "gist_questions": [
                    "What is the text mainly about?",
                    "How does Marta feel about the trip?"
                ],
                "detail_questions": [
                    "Where is Marta going?",
                    "Why is she travelling by bus?",
                    "What does she want to do on Saturday?"
                ],
                "post_task": "Ask the student to describe a trip they would like to take."
            },
            "B1_B2": {
                "target_vocabulary": ["destination", "experience", "journey", "schedule", "budget"],
                "warm_up": [
                    "What makes a trip memorable?",
                    "Do you prefer detailed travel plans or spontaneous travel?",
                    "What problems can happen during a trip?"
                ],
                "reading_passage": (
                    "For many people, travel is more than moving from one place to another. It can be a way to learn, rest, or discover new perspectives. "
                    "Some travellers prefer to plan every detail, including transport, accommodation, and daily activities. Others leave space for spontaneity, "
                    "believing that unexpected experiences often become the most memorable part of a journey. In both cases, travel usually teaches people how to adapt, "
                    "communicate, and make decisions in unfamiliar situations."
                ),
                "listening_script": (
                    "Today we will listen to a short talk about why people travel. Some people travel to relax, while others travel to learn about different cultures. "
                    "The speaker explains that travel often improves communication skills and helps people become more flexible when facing unfamiliar situations."
                ),
                "pre_task_questions": [
                    "Why do people travel?",
                    "What benefits can travel bring to a person?"
                ],
                "gist_questions": [
                    "What is the speaker’s main point about travel?",
                    "What general benefits of travel are mentioned?"
                ],
                "detail_questions": [
                    "What is the difference between planners and spontaneous travellers?",
                    "What skills can improve through travel?",
                    "Why do unfamiliar situations matter in travel?"
                ],
                "post_task": "Ask the student to explain whether travel is more educational or relaxing."
            }
        },
        "es": {
            "A1_A2": {
                "target_vocabulary": ["viaje", "boleto", "hotel", "visitar", "maleta"],
                "warm_up": [
                    "¿Has viajado a otra ciudad o país?",
                    "¿Qué necesita una persona antes de un viaje?",
                    "¿Qué lugares te gusta visitar?"
                ],
                "reading_passage": (
                    "Marta está planeando un viaje a Ankara para el fin de semana. Quiere viajar en autobús porque es más barato que el avión. "
                    "Ya tiene una maleta pequeña, zapatos cómodos y una lista de lugares para visitar. El sábado por la mañana quiere ver la ciudad antigua, "
                    "comer comida local y comprar un regalo para su familia. Está emocionada porque no viaja muy a menudo."
                ),
                "listening_script": (
                    "Buenos días. Hoy hablamos sobre planes de viaje. Marta va a Ankara este fin de semana. "
                    "Va en autobús y quiere visitar la ciudad antigua, probar comida local y comprar un recuerdo. "
                    "Está emocionada porque no viaja muy seguido."
                ),
                "pre_task_questions": [
                    "¿Qué prepara normalmente una persona antes de un viaje?",
                    "¿Qué palabras esperas escuchar en un texto sobre viajes?"
                ],
                "gist_questions": [
                    "¿De qué trata principalmente el texto?",
                    "¿Cómo se siente Marta sobre el viaje?"
                ],
                "detail_questions": [
                    "¿A dónde va Marta?",
                    "¿Por qué viaja en autobús?",
                    "¿Qué quiere hacer el sábado?"
                ],
                "post_task": "Pide al estudiante que describa un viaje que le gustaría hacer."
            },
            "B1_B2": {
                "target_vocabulary": ["destino", "experiencia", "trayecto", "horario", "presupuesto"],
                "warm_up": [
                    "¿Qué hace que un viaje sea memorable?",
                    "¿Prefieres planear todo o viajar de manera espontánea?",
                    "¿Qué problemas pueden ocurrir durante un viaje?"
                ],
                "reading_passage": (
                    "Para muchas personas, viajar es mucho más que trasladarse de un lugar a otro. Puede ser una forma de aprender, descansar o descubrir nuevas perspectivas. "
                    "Algunos viajeros prefieren planear cada detalle, incluyendo el transporte, el alojamiento y las actividades diarias. Otros dejan espacio para la espontaneidad, "
                    "porque creen que las experiencias inesperadas suelen convertirse en la parte más memorable del viaje. En ambos casos, viajar enseña a adaptarse, comunicarse y tomar decisiones."
                ),
                "listening_script": (
                    "Hoy escucharemos una breve explicación sobre por qué la gente viaja. Algunas personas viajan para descansar y otras para conocer culturas diferentes. "
                    "El hablante explica que viajar mejora la comunicación y ayuda a ser más flexible en situaciones desconocidas."
                ),
                "pre_task_questions": [
                    "¿Por qué viajan las personas?",
                    "¿Qué beneficios puede traer un viaje?"
                ],
                "gist_questions": [
                    "¿Cuál es la idea principal sobre viajar?",
                    "¿Qué beneficios generales del viaje se mencionan?"
                ],
                "detail_questions": [
                    "¿Qué diferencia hay entre los viajeros organizados y los espontáneos?",
                    "¿Qué habilidades puede mejorar una persona al viajar?",
                    "¿Por qué son importantes las situaciones desconocidas?"
                ],
                "post_task": "Pide al estudiante que explique si viajar es más educativo o más relajante."
            }
        },
        "tr": {
            "A1_A2": {
                "target_vocabulary": ["seyahat", "gezi", "bilet", "otel", "ziyaret"],
                "warm_up": [
                    "Daha önce başka bir şehre ya da ülkeye seyahat ettin mi?",
                    "İnsanlar bir yolculuktan önce genellikle nelere ihtiyaç duyar?",
                    "Hangi yerleri ziyaret etmeyi seversin?"
                ],
                "reading_passage": (
                    "Marta hafta sonu için Ankara'ya bir gezi planlıyor. Otobüsle gitmek istiyor çünkü uçaktan daha ucuz. "
                    "Küçük bir çantası, rahat ayakkabıları ve ziyaret etmek istediği yerlerin bir listesi hazır. Cumartesi sabahı eski şehri görmek, "
                    "yerel yemekler yemek ve ailesi için bir hediye almak istiyor. Çok sık seyahat etmediği için heyecanlı."
                ),
                "listening_script": (
                    "Günaydın arkadaşlar. Bugün seyahat planları hakkında konuşuyoruz. Marta bu hafta sonu Ankara'ya gidiyor. "
                    "Otobüsle gidiyor ve eski şehri ziyaret etmek, yerel yemekler denemek ve bir hatıra almak istiyor. "
                    "Çok sık seyahat etmediği için heyecanlı hissediyor."
                ),
                "pre_task_questions": [
                    "İnsanlar bir yolculuktan önce genellikle ne hazırlar?",
                    "Seyahatle ilgili bir metinde hangi kelimeleri duymayı beklersin?"
                ],
                "gist_questions": [
                    "Metin genel olarak ne hakkında?",
                    "Marta gezi hakkında nasıl hissediyor?"
                ],
                "detail_questions": [
                    "Marta nereye gidiyor?",
                    "Neden otobüsle gidiyor?",
                    "Cumartesi günü ne yapmak istiyor?"
                ],
                "post_task": "Öğrenciden yapmak isteyeceği bir geziyi tarif etmesini isteyin."
            },
            "B1_B2": {
                "target_vocabulary": ["varış noktası", "deneyim", "yolculuk", "program", "bütçe"],
                "warm_up": [
                    "Bir geziyi unutulmaz yapan şey nedir?",
                    "Detaylı plan yapmayı mı yoksa spontane seyahati mi tercih edersin?",
                    "Yolculuk sırasında ne gibi sorunlar yaşanabilir?"
                ],
                "reading_passage": (
                    "Birçok insan için seyahat, bir yerden başka bir yere gitmekten daha fazlasıdır. Öğrenmenin, dinlenmenin veya yeni bakış açıları keşfetmenin bir yolu olabilir. "
                    "Bazı gezginler ulaşım, konaklama ve günlük etkinlikler dahil her ayrıntıyı planlamayı tercih eder. Diğerleri ise spontane davranmaya yer bırakır; "
                    "çünkü beklenmedik deneyimlerin yolculuğun en unutulmaz kısmı olduğuna inanırlar. Her iki durumda da seyahat, insanlara uyum sağlamayı, "
                    "iletişim kurmayı ve alışılmadık durumlarda karar vermeyi öğretir."
                ),
                "listening_script": (
                    "Bugün insanların neden seyahat ettiğine dair kısa bir konuşma dinleyeceğiz. Bazıları dinlenmek için, bazıları ise farklı kültürleri öğrenmek için seyahat eder. "
                    "Konuşmacı, seyahatin iletişim becerilerini geliştirdiğini ve insanlara alışılmadık durumlarla karşılaştıklarında daha esnek olmayı öğrettiğini açıklıyor."
                ),
                "pre_task_questions": [
                    "İnsanlar neden seyahat eder?",
                    "Seyahat bir insana ne gibi faydalar sağlayabilir?"
                ],
                "gist_questions": [
                    "Konuşmacının seyahat hakkındaki ana fikri nedir?",
                    "Seyahatin hangi genel faydaları belirtiliyor?"
                ],
                "detail_questions": [
                    "Plan yapanlarla spontane gezginler arasındaki fark nedir?",
                    "Seyahat yoluyla hangi beceriler gelişebilir?",
                    "Alışılmadık durumlar neden önemlidir?"
                ],
                "post_task": "Öğrenciden seyahatin daha çok eğitici mi yoksa rahatlatıcı mı olduğunu açıklamasını isteyin."
            }
        }
    },

    "food": {
        "en": {
            "A1_A2": {
                "target_vocabulary": ["food", "meal", "restaurant", "cook", "breakfast"],
                "warm_up": [
                    "What food do you like most?",
                    "What do you usually eat for breakfast?",
                    "Can you cook any simple meal?"
                ],
                "reading_passage": (
                    "Leo likes food that is simple and fresh. In the morning, he usually eats bread, cheese, and fruit. "
                    "At lunchtime, he sometimes goes to a small restaurant near his office. His favourite meal is grilled chicken with rice and salad. "
                    "At the weekend, he enjoys cooking with his sister because they can try new recipes together."
                ),
                "listening_script": (
                    "Hello everyone. Today we are listening to a short text about food habits. Leo enjoys simple meals like bread, cheese, fruit, and grilled chicken. "
                    "He also likes cooking with his sister at the weekend."
                ),
                "pre_task_questions": [
                    "What meals do people eat during the day?",
                    "What food words do you already know?"
                ],
                "gist_questions": [
                    "What is the text mainly about?",
                    "What kind of food does Leo like?"
                ],
                "detail_questions": [
                    "What does Leo eat in the morning?",
                    "Where does he sometimes go at lunchtime?",
                    "Who does he cook with at the weekend?"
                ],
                "post_task": "Ask the student to describe their favourite meal."
            }
        },
        "es": {
            "A1_A2": {
                "target_vocabulary": ["comida", "comer", "restaurante", "cocinar", "desayuno"],
                "warm_up": [
                    "¿Qué comida te gusta más?",
                    "¿Qué desayunas normalmente?",
                    "¿Sabes cocinar algo sencillo?"
                ],
                "reading_passage": (
                    "A Leo le gusta la comida simple y fresca. Por la mañana suele comer pan, queso y fruta. "
                    "Al mediodía, a veces va a un restaurante pequeño cerca de su oficina. Su comida favorita es pollo a la plancha con arroz y ensalada. "
                    "El fin de semana le gusta cocinar con su hermana porque pueden probar recetas nuevas juntos."
                ),
                "listening_script": (
                    "Hola a todos. Hoy escucharemos un texto corto sobre hábitos de comida. A Leo le gustan comidas simples como pan, queso, fruta y pollo a la plancha. "
                    "También le gusta cocinar con su hermana los fines de semana."
                ),
                "pre_task_questions": [
                    "¿Qué comidas hace una persona durante el día?",
                    "¿Qué palabras sobre comida conoces ya?"
                ],
                "gist_questions": [
                    "¿De qué trata principalmente el texto?",
                    "¿Qué tipo de comida le gusta a Leo?"
                ],
                "detail_questions": [
                    "¿Qué come Leo por la mañana?",
                    "¿A dónde va a veces al mediodía?",
                    "¿Con quién cocina el fin de semana?"
                ],
                "post_task": "Pide al estudiante que describa su comida favorita."
            }
        },
        "tr": {
            "A1_A2": {
                "target_vocabulary": ["yemek", "öğün", "restoran", "pişirmek", "kahvaltı"],
                "warm_up": [
                    "En çok hangi yemeği seversin?",
                    "Kahvaltıda genellikle ne yersin?",
                    "Basit bir yemek pişirebilir misin?"
                ],
                "reading_passage": (
                    "Leo sade ve taze yemekleri sever. Sabahları genellikle ekmek, peynir ve meyve yer. "
                    "Öğle vakti bazen ofisinin yakınındaki küçük bir restorana gider. En sevdiği yemek pilav ve salatayla servis edilen ızgara tavuktur. "
                    "Hafta sonları kız kardeşiyle yemek yapmaktan hoşlanır çünkü birlikte yeni tarifler deneyebilirler."
                ),
                "listening_script": (
                    "Herkese merhaba. Bugün yemek alışkanlıklarıyla ilgili kısa bir metin dinliyoruz. Leo ekmek, peynir, meyve ve ızgara tavuk gibi sade öğünleri seviyor. "
                    "Ayrıca hafta sonu kız kardeşiyle yemek yapmayı da seviyor."
                ),
                "pre_task_questions": [
                    "İnsanlar gün içinde hangi öğünleri yer?",
                    "Yemekle ilgili zaten bildiğin hangi kelimeler var?"
                ],
                "gist_questions": [
                    "Metin genel olarak ne hakkında?",
                    "Leo nasıl yemekleri seviyor?"
                ],
                "detail_questions": [
                    "Leo sabah ne yiyor?",
                    "Öğle vakti bazen nereye gidiyor?",
                    "Hafta sonu kiminle yemek yapıyor?"
                ],
                "post_task": "Öğrenciden en sevdiği yemeği anlatmasını isteyin."
            }
        }
    }
}


def _language_bank_key(topic: str) -> str:
    return str(topic or "").strip().casefold()


def _language_bank_bucket(level: str) -> str:
    if level in ("A1", "A2"):
        return "A1_A2"
    if level in ("B1", "B2"):
        return "B1_B2"
    return "C1_C2"


def _get_language_bank_entry(topic: str, level: str, material_lang: str) -> dict:
    topic_key = _language_bank_key(topic)
    lang_key = str(material_lang).strip().lower()
    if lang_key not in {"en", "es", "tr"}:
        lang_key = "en"

    bucket = _language_bank_bucket(level)
    topic_block = LANGUAGE_CONTENT_BANK.get(topic_key, {})
    lang_block = topic_block.get(lang_key, {})
    entry = lang_block.get(bucket)

    if isinstance(entry, dict):
        return entry

    if bucket == "C1_C2":
        fallback = lang_block.get("B1_B2")
        if isinstance(fallback, dict):
            return fallback

    return {}


def _language_target_vocab(topic: str, level: str) -> list[str]:
    entry = _get_language_bank_entry(
        topic,
        level,
        get_student_material_language(st.session_state.get("quick_plan_subject", "English")),
    )
    if entry.get("target_vocabulary"):
        return entry["target_vocabulary"]

    topic = _topic_clean(topic)
    material_lang = get_student_material_language(st.session_state.get("quick_plan_subject", "English"))

    if material_lang == "tr":
        if level in ("A1", "A2"):
            return [topic, "örnek", "fikir", "kullanım", "günlük hayat"]
        if level in ("B1", "B2"):
            return [topic, "deneyim", "görüş", "avantaj", "durum"]
        return [topic, "bakış açısı", "etki", "zorluk", "yorumlama"]

    if level in ("A1", "A2"):
        return [topic, "example", "idea", "use", "daily life"]
    if level in ("B1", "B2"):
        return [topic, "experience", "opinion", "advantage", "situation"]
    return [topic, "perspective", "impact", "challenge", "interpretation"]


def _language_warmup_questions(topic: str, stage: str, level: str) -> list[str]:
    material_lang = get_student_material_language(st.session_state.get("quick_plan_subject", "English"))
    entry = _get_language_bank_entry(topic, level, material_lang)
    if entry.get("warm_up"):
        return entry["warm_up"]

    if material_lang == "tr":
        if level in ("A1", "A2"):
            return [
                f"{topic} hakkında hangi kelimeleri biliyorsun?",
                f"{topic} ilgini çekiyor mu? Neden?",
                f"Daha önce {topic} gördün ya da kullandın mı?",
            ]
        if level in ("B1", "B2"):
            return [
                f"{topic} hakkında zaten ne biliyorsun?",
                f"{topic} gerçek hayatta nerede karşımıza çıkar?",
                f"{topic} hakkında ne düşünüyorsun?",
            ]
        return [
            f"Sence {topic} neden farklı görüşlere yol açabilir?",
            f"{topic} ile hangi kişisel ya da toplumsal deneyimi ilişkilendirebilirsin?",
            f"{topic} ile ilgili en ilginç ya da tartışmalı kısım hangisi?",
        ]

    if material_lang == "es":
        if level in ("A1", "A2"):
            return [
                f"¿Qué palabras conoces sobre {topic}?",
                f"¿Te gusta o te interesa {topic}? ¿Por qué?",
                f"¿Has visto o usado {topic} antes?",
            ]
        if level in ("B1", "B2"):
            return [
                f"¿Qué sabes ya sobre {topic}?",
                f"¿Dónde aparece {topic} en la vida real?",
                f"¿Qué opinión tienes sobre {topic}?",
            ]
        return [
            f"¿Por qué crees que {topic} puede generar opiniones diferentes?",
            f"¿Qué experiencia personal o social relacionas con {topic}?",
            f"¿Qué aspecto de {topic} te parece más interesante o discutible?",
        ]

    if level in ("A1", "A2"):
        return [
            f"What words do you already know about {topic}?",
            f"Do you like or find {topic} interesting? Why?",
            f"Have you seen or used {topic} before?",
        ]
    if level in ("B1", "B2"):
        return [
            f"What do you already know about {topic}?",
            f"Where does {topic} appear in real life?",
            f"What is your opinion about {topic}?",
        ]
    return [
        f"Why might {topic} lead to different opinions?",
        f"What personal or social experience can you connect to {topic}?",
        f"What part of {topic} seems most interesting or debatable to you?",
    ]


def _language_reading_text(topic: str, level: str, material_lang: str) -> str:
    entry = _get_language_bank_entry(topic, level, material_lang)
    if entry.get("reading_passage"):
        return entry["reading_passage"]

    topic_cap = _capitalize_topic(topic)

    if material_lang == "tr":
        if level == "A1":
            return (
                f"{topic_cap} günlük hayatın bir parçasıdır. Birçok insan evde, okulda ve arkadaşlarıyla {topic} hakkında konuşur. "
                f"Bu derste öğrenci basit kelimeler öğrenir ve {topic} hakkında temel fikirler ifade edebilir. "
                f"Dersin sonunda öğrenci kişisel bir örnek verebilir."
            )
        if level == "A2":
            return (
                f"{topic_cap} günlük yaşamda birçok durumda karşımıza çıkar. Bazı insanlar bunu sık kullanır, bazıları ise çok fazla düşünmez. "
                f"{topic} hakkında konuşmak, öğrencilerin yararlı kelimeleri kullanmasını, beğeni ve tercihlerini ifade etmesini ve deneyimlerinden basit örnekler vermesini sağlar."
            )
        if level in ("B1", "B2"):
            return (
                f"{topic_cap}, iletişim için yararlı bir konudur çünkü insanların deneyimler, görüşler ve gerçek yaşam durumları hakkında konuşmasına olanak tanır. "
                f"Öğrenciler {topic} hakkında bir metinle çalıştıklarında yalnızca yeni kelimeler öğrenmez, aynı zamanda fikirlerini daha açık ifade etmeyi de uygularlar. "
                f"Ayrıca, konuyu kişisel deneyimle ilişkilendirmek öğrenmeyi daha kalıcı hâle getirir."
            )
        return (
            f"{topic_cap}, kişisel deneyim, toplumsal bakış açıları ve dildeki incelikleri incelemeye olanak sağladığı için analiz açısından zengin bir konudur. "
            f"Akademik bir bağlamda bu konu üzerinde çalışmak, öğrencilerin bilgiyi yorumlamasına, görüşlerini gerekçelendirmesine ve daha net cevaplar üretmesine yardımcı olur. "
            f"Metni gerçek yaşam bağlamlarıyla ne kadar çok ilişkilendirirlerse, anlayışları da o kadar derinleşir."
        )

    if material_lang == "es":
        if level == "A1":
            return (
                f"{topic_cap} es parte de la vida diaria. Muchas personas hablan de {topic} en casa, en la escuela y con sus amigos. "
                f"En esta clase, el estudiante aprende palabras simples y puede decir ideas básicas sobre {topic}. "
                f"Al final, el estudiante puede dar un ejemplo personal."
            )
        if level == "A2":
            return (
                f"{topic_cap} aparece en muchas situaciones cotidianas. Algunas personas lo usan con frecuencia y otras no piensan mucho en ello. "
                f"Hablar sobre {topic} ayuda a los estudiantes a practicar vocabulario útil, expresar gustos y dar ejemplos simples de su experiencia."
            )
        if level in ("B1", "B2"):
            return (
                f"{topic_cap} es un tema útil para la comunicación porque permite hablar de experiencias, opiniones y situaciones de la vida real. "
                f"Cuando los estudiantes trabajan con un texto sobre {topic}, no solo aprenden vocabulario nuevo, sino que también practican cómo explicar ideas con más claridad. "
                f"Además, conectar el tema con experiencias personales hace que el aprendizaje sea más memorable."
            )
        return (
            f"{topic_cap} es un tema rico para el análisis porque permite explorar experiencias personales, perspectivas sociales y matices del lenguaje. "
            f"En un contexto académico, trabajar este tema ayuda a los estudiantes a interpretar información, justificar opiniones y desarrollar respuestas más precisas. "
            f"Cuanto más conectan el texto con contextos reales, más profunda se vuelve la comprensión."
        )

    if level == "A1":
        return (
            f"{topic_cap} is part of daily life. Many people talk about {topic} at home, at school, and with friends. "
            f"In this lesson, the student learns simple words and can give basic ideas about {topic}. "
            f"At the end, the student can give one personal example."
        )
    if level == "A2":
        return (
            f"{topic_cap} appears in many everyday situations. Some people use it often, while others do not think about it very much. "
            f"Talking about {topic} helps students practice useful vocabulary, express likes and dislikes, and give simple examples from experience."
        )
    if level in ("B1", "B2"):
        return (
            f"{topic_cap} is a useful topic for communication because it allows people to talk about experiences, opinions, and real-life situations. "
            f"When students work with a text about {topic}, they not only learn new vocabulary but also practice how to explain ideas more clearly. "
            f"In addition, connecting the topic to personal experience makes learning more memorable."
        )
    return (
        f"{topic_cap} is a rich topic for analysis because it allows learners to explore personal experience, social perspectives, and nuance in language. "
        f"In an academic setting, working with this topic helps students interpret information, justify opinions, and produce more precise responses. "
        f"The more they connect the text to real contexts, the deeper their understanding becomes."
    )


def _language_listening_text(topic: str, level: str, material_lang: str) -> str:
    entry = _get_language_bank_entry(topic, level, material_lang)
    if entry.get("listening_script"):
        return entry["listening_script"]

    topic_cap = _capitalize_topic(topic)

    if material_lang == "tr":
        if level in ("A1", "A2"):
            return (
                f"Merhaba. Bugün {topic} hakkında konuşacağız. Bu günlük hayattan bir konudur. "
                f"Önce bazı basit fikirleri dinleyeceğiz ve sonra kısa soruları cevaplayacağız. "
                f"Daha sonra her öğrenci {topic} ile ilgili kişisel bir örnek verecek."
            )
        if level in ("B1", "B2"):
            return (
                f"Günaydın. Bugünkü ders {topic} üzerine odaklanıyor. Önce ana fikirleri dinleyeceğiz, sonra ayrıntılara dikkat edeceğiz "
                f"ve en sonunda konuyu kendi deneyimlerimizle ilişkilendireceğiz. Bu tür bir etkinlik anlama becerisini ve konuşma güvenini geliştirir."
            )
        return (
            f"Günaydın. Bugünkü odağımız {topic}. Ana fikirleri, incelikleri ve önemli ayrıntıları belirlemek için kısa bir metin dinleyeceğiz. "
            f"Daha sonra bu konunun gerçek yaşamla ve farklı bakış açılarıyla nasıl bağlantılı olduğunu tartışacağız."
        )

    if material_lang == "es":
        if level in ("A1", "A2"):
            return (
                f"Hola. Hoy vamos a hablar sobre {topic}. Es un tema que aparece en la vida diaria. "
                f"Primero escucharemos algunas ideas simples y luego responderemos preguntas cortas. "
                f"Después, cada estudiante dará un ejemplo personal relacionado con {topic}."
            )
        if level in ("B1", "B2"):
            return (
                f"Buenos días. La clase de hoy se centra en {topic}. Primero escucharemos las ideas principales, luego prestaremos atención a los detalles, "
                f"y finalmente relacionaremos el tema con nuestras propias experiencias. Este tipo de actividad ayuda a mejorar la comprensión y la confianza al hablar."
            )
        return (
            f"Buenos días. El enfoque de hoy es {topic}. Escucharemos un breve texto para identificar ideas principales, matices y detalles relevantes. "
            f"Después discutiremos cómo este tema se conecta con experiencias reales y con diferentes puntos de vista."
        )

    if level in ("A1", "A2"):
        return (
            f"Hello. Today we are going to talk about {topic}. It is a topic from daily life. "
            f"First, we will listen to some simple ideas and then answer short questions. "
            f"After that, each student will give one personal example related to {topic}."
        )
    if level in ("B1", "B2"):
        return (
            f"Good morning. Today’s class focuses on {topic}. First, we will listen for the main ideas, then pay attention to details, "
            f"and finally connect the topic to our own experiences. This kind of activity helps students improve comprehension and speaking confidence."
        )
    return (
        f"Good morning. Today’s focus is {topic}. We will listen to a short text in order to identify main ideas, nuance, and relevant details. "
        f"After that, we will discuss how the topic connects to real experience and to different perspectives."
    )


def _language_text_questions(topic: str, level: str, plan_lang: str) -> tuple[list[str], list[str], list[str]]:
    material_lang = get_student_material_language(st.session_state.get("quick_plan_subject", "English"))
    entry = _get_language_bank_entry(topic, level, material_lang)

    if entry:
        pre = entry.get("pre_task_questions", [])
        gist = entry.get("gist_questions", [])
        detail = entry.get("detail_questions", [])
        if pre or gist or detail:
            return pre, gist, detail

    if plan_lang == "tr":
        if level in ("A1", "A2"):
            pre = [
                f"{topic} hakkında zaten ne biliyorsun?",
                f"{topic} hakkında hangi kelimeleri duymayı ya da okumayı beklersin?",
            ]
            gist = [
                "Metnin ana fikri nedir?",
                "Metin olumlu, olumsuz yoksa nötr mü?",
            ]
            detail = [
                "Metinden bir özel ayrıntı söyle.",
                "Metinde hangi örnek geçiyor?",
                "Metindeki kişi ne yapıyor ya da ne düşünüyor?",
            ]
            return pre, gist, detail

        if level in ("B1", "B2"):
            pre = [
                f"{topic} ile hangi sorunları, avantajları ya da deneyimleri ilişkilendiriyorsun?",
                "Metinde nasıl bir bilgi yer almasını bekliyorsun?",
            ]
            gist = [
                "Metnin temel mesajı nedir?",
                "Yazar ya da konuşmacı en çok hangi fikri vurgulamak istiyor?",
            ]
            detail = [
                "Ana fikri destekleyen iki ayrıntı hangileri?",
                "Metinde hangi somut örnek veriliyor?",
                "Konu gerçek yaşamla nasıl ilişkilendiriliyor?",
            ]
            return pre, gist, detail

        pre = [
            f"{topic} hakkında hangi farklı bakış açıları ortaya çıkabilir?",
            "Metinde nasıl bir ton ya da duruş bulmayı bekliyorsun?",
        ]
        gist = [
            "Metnin baskın tezi ya da ana fikri nedir?",
            "Hangi önemli karşıtlık ya da incelik yer alıyor?",
        ]
        detail = [
            "Hangi ayrıntı ana argümanı en iyi destekliyor?",
            "Metinden hangi çıkarım yapılabilir?",
            "Metnin hangi bölümü yazarın ya da konuşmacının tutumunu en açık biçimde gösteriyor?",
        ]
        return pre, gist, detail

    if plan_lang == "es":
        if level in ("A1", "A2"):
            pre = [
                f"¿Qué sabes ya sobre {topic}?",
                f"¿Qué palabras esperas escuchar o leer sobre {topic}?",
            ]
            gist = [
                "¿Cuál es la idea principal del texto?",
                "¿El texto presenta una idea positiva, negativa o neutral?",
            ]
            detail = [
                "Menciona una información específica del texto.",
                "¿Qué ejemplo aparece en el texto?",
                "¿Qué hace o piensa la persona del texto?",
            ]
            return pre, gist, detail

        if level in ("B1", "B2"):
            pre = [
                f"¿Qué problemas, ventajas o experiencias relacionas con {topic}?",
                "¿Qué tipo de información crees que aparecerá en el texto?",
            ]
            gist = [
                "¿Cuál es el mensaje central del texto?",
                "¿Qué idea quiere destacar más el autor o hablante?",
            ]
            detail = [
                "¿Qué dos detalles apoyan la idea principal?",
                "¿Qué ejemplo concreto aparece en el texto?",
                "¿Qué relación se establece entre el tema y la vida real?",
            ]
            return pre, gist, detail

        pre = [
            f"¿Qué perspectivas distintas pueden aparecer sobre {topic}?",
            "¿Qué tono o postura esperas encontrar en el texto?",
        ]
        gist = [
            "¿Cuál es la tesis o idea dominante del texto?",
            "¿Qué matiz o contraste importante aparece?",
        ]
        detail = [
            "¿Qué detalle apoya mejor la idea principal?",
            "¿Qué inferencia se puede hacer a partir del texto?",
            "¿Qué parte del texto muestra más claramente la postura del autor o hablante?",
        ]
        return pre, gist, detail

    if level in ("A1", "A2"):
        pre = [
            f"What do you already know about {topic}?",
            f"What words do you expect to hear or read about {topic}?",
        ]
        gist = [
            "What is the main idea of the text?",
            "Is the text positive, negative, or neutral?",
        ]
        detail = [
            "Name one specific detail from the text.",
            "What example appears in the text?",
            "What does the person in the text do or think?",
        ]
        return pre, gist, detail

    if level in ("B1", "B2"):
        pre = [
            f"What problems, advantages, or experiences do you connect with {topic}?",
            "What type of information do you expect to appear in the text?",
        ]
        gist = [
            "What is the central message of the text?",
            "What idea does the writer or speaker want to highlight most?",
        ]
        detail = [
            "Which two details support the main idea?",
            "What concrete example appears in the text?",
            "How is the topic connected to real life?",
        ]
        return pre, gist, detail

    pre = [
        f"What different perspectives might appear about {topic}?",
        "What tone or position do you expect to find in the text?",
    ]
    gist = [
        "What is the dominant thesis or idea of the text?",
        "What important contrast or nuance appears?",
    ]
    detail = [
        "Which detail best supports the main argument?",
        "What inference can be made from the text?",
        "Which part of the text reveals the author’s or speaker’s position most clearly?",
    ]
    return pre, gist, detail


def _language_plan(subject: str, stage: str, level: str, purpose: str, topic: str) -> dict:
    plan_lang = get_plan_language()
    material_lang = get_student_material_language(subject)
    topic_cap = _capitalize_topic(topic)

    warm = _language_warmup_questions(topic, stage, level)
    pre_q, gist_q, detail_q = _language_text_questions(topic, level, plan_lang)
    vocab = _get_language_bank_entry(topic, level, material_lang).get("target_vocabulary") or _language_target_vocab(topic, level)

    use_reading = purpose in ("introduce_concept", "review_topic", "diagnose_difficulty")
    use_listening = purpose == "practice_skill"

    core_material = {
        "target_vocabulary": vocab,
        "pre_task_questions": pre_q,
        "gist_questions": gist_q,
        "detail_questions": detail_q,
        "post_task": _get_language_bank_entry(topic, level, material_lang).get("post_task") or qlp_txt(
            f"Ask the student to connect the text to one personal experience with {topic}.",
            f"Pide al estudiante que conecte el texto con una experiencia personal sobre {topic}.",
            f"Öğrenciden metni {topic} ile ilgili kişisel bir deneyimle ilişkilendirmesini isteyin.",
        ),
    }

    return {
        "title": f"{subject_label(subject)}: {topic_cap}",
        "objective": qlp_txt(
            f"Students will develop their language skills while working on {topic_cap}.",
            f"El estudiante desarrollará sus habilidades lingüísticas mientras trabaja con {topic_cap}.",
            f"Öğrenciler {topic_cap} üzerinde çalışırken dil becerilerini geliştirecekler.",
        ),
        "recommended_level": level,
        "plan_language": plan_lang,
        "student_material_language": material_lang,
        "success_criteria": [
            qlp_txt(
                f"The student can answer the main idea and detail questions about {topic}.",
                f"El estudiante puede responder preguntas globales y de detalle sobre {topic}.",
                f"Öğrenci, {topic} ile ilgili ana fikir ve ayrıntı sorularını cevaplayabilir.",
            ),
            qlp_txt(
                "The student uses at least 3 useful words from the lesson.",
                "El estudiante usa al menos 3 palabras útiles de la clase.",
                "Öğrenci dersten en az 3 yararlı kelime kullanır.",
            ),
        ],
        "warm_up": warm,
        "main_activity": [
            qlp_txt(
                f"Activate prior knowledge about {topic}.",
                f"Activa conocimientos previos sobre {topic}.",
                f"{topic} ile ilgili önceki bilgileri etkinleştirin.",
            ),
            qlp_txt(
                "Guide the student from global understanding to detail.",
                "Guía al estudiante desde la comprensión global hacia el detalle.",
                "Öğrenciyi genel anlamadan ayrıntıya doğru yönlendirin.",
            ),
        ],
        "core_examples": [
            qlp_txt(
                "Model one complete answer before asking for independent production.",
                "Modela una respuesta completa antes de pedir producción independiente.",
                "Bağımsız üretim istemeden önce tam bir cevabı modelleyin.",
            ),
            qlp_txt(
                "Recycle target vocabulary during feedback.",
                "Recicla el vocabulario objetivo durante la retroalimentación.",
                "Geri bildirim sırasında hedef kelimeleri yeniden kullanın.",
            ),
        ],
        "guided_practice": [
            qlp_txt(
                "Do the pre-task questions first, then the gist questions, and finally the detail questions.",
                "Haz primero las preguntas previas, luego las globales y por último las de detalle.",
                "Önce ön hazırlık sorularını, sonra genel anlama sorularını ve en son ayrıntı sorularını yapın.",
            ),
            qlp_txt(
                "If the student struggles, return to one sentence or one key idea.",
                "Si el estudiante tiene dificultad, vuelve a una oración o idea clave.",
                "Öğrenci zorlanırsa bir cümleye ya da tek bir ana fikre geri dönün.",
            ),
        ],
        "practice_questions": gist_q + detail_q,
        "freer_task": [
            qlp_txt(
                f"Student gives a short spoken or written response about {topic}.",
                f"El estudiante da una respuesta breve oral o escrita sobre {topic}.",
                f"Öğrenci {topic} hakkında kısa bir sözlü ya da yazılı cevap verir.",
            ),
            qlp_txt(
                "Teacher gives quick feedback on clarity, vocabulary, and accuracy.",
                "El profesor da retroalimentación breve sobre claridad, vocabulario y precisión.",
                "Öğretmen açıklık, kelime kullanımı ve doğruluk hakkında kısa geri bildirim verir.",
            ),
        ],
        "wrap_up": [
            qlp_txt(
                "Review the key vocabulary and one main idea from the text.",
                "Repasa el vocabulario clave y una idea principal del texto.",
                "Anahtar kelimeleri ve metindeki bir ana fikri gözden geçirin.",
            ),
            qlp_txt(
                "Ask the student to summarize the text in 1–2 sentences.",
                "Pide al estudiante que resuma el texto en 1–2 oraciones.",
                "Öğrenciden metni 1-2 cümleyle özetlemesini isteyin.",
            ),
        ],
        "teacher_moves": _teacher_move_block("language", purpose),
        "extension_task": qlp_txt(
            f"Ask the student to create 2 extra questions about {topic} and answer them.",
            f"Pide al estudiante que cree 2 preguntas extra sobre {topic} y las responda.",
            f"Öğrenciden {topic} hakkında 2 ek soru oluşturmasını ve bunları cevaplamasını isteyin.",
        ),
        "homework": qlp_txt(
            f"Review today’s language from the lesson on {topic}.",
            f"Repasa el lenguaje trabajado hoy sobre {topic}.",
            f"Bugün derste {topic} hakkında işlenen dili gözden geçirin.",
        ),
        "reading_passage": _language_reading_text(topic, level, material_lang) if use_reading else "",
        "listening_script": _language_listening_text(topic, level, material_lang) if use_listening else "",
        "core_material": core_material,
    }


# -------------------------
# MATH / SCIENCE / MUSIC / STUDY SKILLS
# -------------------------

def _math_warmup_questions(topic: str, band: str) -> list[str]:
    if get_plan_language() == "tr":
        if band == "beginner_band":
            return [
                f"{topic} ile daha önce nerede karşılaştın?",
                f"{topic} konusunun hangi kısmı kolay ya da zor görünüyor?",
                f"{topic} hakkında zaten ne hatırlıyorsun?",
            ]
        if band == "intermediate_band":
            return [
                f"{topic} hakkında hangi kuralı ya da fikri hatırlıyorsun?",
                f"{topic} üzerinde çalışırken hangi hata sık yapılır?",
                f"{topic} konusunu kendi sözlerinle nasıl açıklarsın?",
            ]
        return [
            f"{topic} ile ilgili bir görevi çözmek için en verimli strateji ne olurdu?",
            f"{topic} konusunda hangi kavramsal hata ortaya çıkabilir?",
            f"{topic} çözerken her adımı nasıl gerekçelendirirdin?",
        ]

    if get_plan_language() == "es":
        if band == "beginner_band":
            return [
                f"¿Dónde has visto {topic} antes?",
                f"¿Qué parte de {topic} te parece fácil o difícil?",
                f"¿Qué recuerdas ya sobre {topic}?",
            ]
        if band == "intermediate_band":
            return [
                f"¿Qué regla o idea recuerdas sobre {topic}?",
                f"¿Qué error suele pasar cuando trabajas con {topic}?",
                f"¿Cómo explicarías {topic} con tus propias palabras?",
            ]
        return [
            f"¿Qué estrategia sería más eficiente para resolver una tarea sobre {topic}?",
            f"¿Qué tipo de error conceptual puede aparecer en {topic}?",
            f"¿Cómo justificarías cada paso al resolver {topic}?",
        ]

    if band == "beginner_band":
        return [
            f"Where have you seen {topic} before?",
            f"What part of {topic} seems easy or difficult?",
            f"What do you already remember about {topic}?",
        ]
    if band == "intermediate_band":
        return [
            f"What rule or idea do you remember about {topic}?",
            f"What mistake often happens when working with {topic}?",
            f"How would you explain {topic} in your own words?",
        ]
    return [
        f"What strategy would be most efficient for solving a task about {topic}?",
        f"What conceptual error might appear in {topic}?",
        f"How would you justify each step when solving {topic}?",
    ]


def _math_material(topic: str) -> dict:
    if get_plan_language() == "tr":
        return {
            "starter_problem": f"Başlangıç problemi: {topic} ile ilgili basit bir görev oluşturun ve öğrenciden ilk adımı açıklamasını isteyin.",
            "worked_example": [
                f"{topic} üzerine çözümlü örnek:",
                "1. Önemli bilgileri belirleyin.",
                "2. Hangi kuralın ya da yöntemin kullanılacağına karar verin.",
                "3. Adım adım çözün.",
                "4. Cevabın mantıklı olup olmadığını kontrol edin.",
            ],
            "independent_practice": [
                f"{topic} hakkında 2 kısa alıştırma çözün.",
                f"Ardından {topic} ile ilgili 1 yeni alıştırma oluşturun.",
            ],
            "common_error_alert": f"Yaygın hata: önce doğru kuralı ya da yöntemi belirlemeden {topic} çözmeye çalışmak.",
        }

    if get_plan_language() == "es":
        return {
            "starter_problem": f"Problema inicial: crea una tarea sencilla relacionada con {topic} y pide al estudiante que explique el primer paso.",
            "worked_example": [
                f"Ejemplo resuelto sobre {topic}:",
                "1. Identifica la información importante.",
                "2. Decide qué regla o procedimiento usar.",
                "3. Resuelve paso a paso.",
                "4. Comprueba si la respuesta tiene sentido.",
            ],
            "independent_practice": [
                f"Resuelve 2 ejercicios cortos sobre {topic}.",
                f"Luego crea 1 ejercicio nuevo sobre {topic}.",
            ],
            "common_error_alert": f"Error común: intentar resolver {topic} sin identificar primero la regla o procedimiento correcto.",
        }

    return {
        "starter_problem": f"Starter problem: create one simple task related to {topic} and ask the student to explain the first step.",
        "worked_example": [
            f"Worked example on {topic}:",
            "1. Identify the important information.",
            "2. Decide which rule or procedure to use.",
            "3. Solve step by step.",
            "4. Check whether the answer makes sense.",
        ],
        "independent_practice": [
            f"Solve 2 short exercises about {topic}.",
            f"Then create 1 new exercise about {topic}.",
        ],
        "common_error_alert": f"Common error: trying to solve {topic} without first identifying the correct rule or procedure.",
    }


def _math_plan(stage: str, level: str, purpose: str, topic: str) -> dict:
    material = _math_material(topic)
    return {
        "title": f"{subject_label('mathematics')}: {_capitalize_topic(topic)}",
        "objective": qlp_txt(
            f"Students will understand and apply {topic} through modeling and guided practice.",
            f"El estudiante comprenderá y aplicará {topic} mediante modelado y práctica guiada.",
            f"Öğrenciler {topic} konusunu modelleme ve rehberli uygulama yoluyla anlayacak ve uygulayacaktır.",
        ),
        "recommended_level": level,
        "plan_language": get_plan_language(),
        "student_material_language": get_plan_language(),
        "success_criteria": [
            qlp_txt(
                f"The student can solve a basic task about {topic}.",
                f"El estudiante puede resolver una tarea básica sobre {topic}.",
                f"Öğrenci {topic} ile ilgili temel bir görevi çözebilir.",
            ),
            qlp_txt(
                "The student can explain at least one step clearly.",
                "El estudiante puede explicar con claridad al menos un paso.",
                "Öğrenci en az bir adımı açıkça açıklayabilir.",
            ),
        ],
        "warm_up": _math_warmup_questions(topic, level),
        "main_activity": [
            qlp_txt(
                f"Present the key concept in {topic}.",
                f"Presenta el concepto clave de {topic}.",
                f"{topic} içindeki temel kavramı sunun.",
            ),
            qlp_txt(
                "Work through one full example before independent practice.",
                "Resuelve un ejemplo completo antes de la práctica independiente.",
                "Bağımsız uygulamadan önce tam bir örneği birlikte çözün.",
            ),
        ],
        "core_examples": [
            material["starter_problem"],
            *material["worked_example"],
        ],
        "guided_practice": [
            qlp_txt(
                "Guide the student through one similar task.",
                "Guía al estudiante en una tarea similar.",
                "Öğrenciyi benzer bir görev boyunca yönlendirin.",
            ),
            qlp_txt(
                "Ask the student to justify each step aloud.",
                "Pide al estudiante que justifique cada paso en voz alta.",
                "Öğrenciden her adımı yüksek sesle gerekçelendirmesini isteyin.",
            ),
        ],
        "practice_questions": [
            qlp_txt("What is the first step?", "¿Cuál es el primer paso?", "İlk adım nedir?"),
            qlp_txt("Why is that step correct?", "¿Por qué ese paso es correcto?", "Bu adım neden doğru?"),
            qlp_txt("Which rule are we using here?", "¿Qué regla estamos usando aquí?", "Burada hangi kuralı kullanıyoruz?"),
            qlp_txt("Can you solve a similar task alone?", "¿Puedes resolver una tarea similar solo?", "Benzer bir görevi tek başına çözebilir misin?"),
        ],
        "freer_task": material["independent_practice"],
        "wrap_up": [
            qlp_txt(
                "Review the rule, formula, or strategy.",
                "Repasa la regla, fórmula o estrategia.",
                "Kuralı, formülü ya da stratejiyi gözden geçirin.",
            ),
            qlp_txt(
                "Ask the student to explain the topic simply.",
                "Pide al estudiante que explique el tema de forma simple.",
                "Öğrenciden konuyu basit şekilde açıklamasını isteyin.",
            ),
        ],
        "teacher_moves": _teacher_move_block("math", purpose),
        "extension_task": qlp_txt(
            f"Ask the student to create one extra problem about {topic} and solve it.",
            f"Pide al estudiante que cree un problema extra sobre {topic} y lo resuelva.",
            f"Öğrenciden {topic} ile ilgili bir ek problem oluşturmasını ve çözmesini isteyin.",
        ),
        "homework": qlp_txt(
            f"Solve 3 more short tasks about {topic}.",
            f"Resuelve 3 tareas cortas más sobre {topic}.",
            f"{topic} hakkında 3 kısa görev daha çözün.",
        ),
        "reading_passage": "",
        "listening_script": "",
        "core_material": material,
    }


def _science_plan(stage: str, level: str, purpose: str, topic: str) -> dict:
    material = {
        "concept_explanation": qlp_txt(
            f"{_capitalize_topic(topic)} should be explained through a simple phenomenon, a clear cause, and one real-life example.",
            f"{_capitalize_topic(topic)} debe explicarse mediante un fenómeno simple, una causa clara y un ejemplo de la vida real.",
            f"{_capitalize_topic(topic)}, basit bir olgu, açık bir neden ve günlük hayattan bir örnek üzerinden açıklanmalıdır.",
        ),
        "real_life_application": qlp_txt(
            f"Ask where {topic} can be seen in daily life.",
            f"Pregunta dónde se puede observar {topic} en la vida diaria.",
            f"{topic} konusunun günlük hayatta nerede görülebileceğini sorun.",
        ),
        "common_error_alert": qlp_txt(
            "Check for memorized definitions without real understanding.",
            "Comprueba si hay definiciones memorizadas sin comprensión real.",
            "Gerçek anlayış olmadan ezberlenmiş tanımlar olup olmadığını kontrol edin.",
        ),
    }

    return {
        "title": f"{subject_label('science')}: {_capitalize_topic(topic)}",
        "objective": qlp_txt(
            f"Students will understand the main idea behind {topic} and connect it to a real example.",
            f"El estudiante comprenderá la idea principal de {topic} y la conectará con un ejemplo real.",
            f"Öğrenciler {topic} konusunun arkasındaki ana fikri anlayacak ve bunu gerçek bir örnekle ilişkilendirecek.",
        ),
        "recommended_level": level,
        "plan_language": get_plan_language(),
        "student_material_language": get_plan_language(),
        "success_criteria": [
            qlp_txt(
                f"The student can explain {topic} in simple words.",
                f"El estudiante puede explicar {topic} con palabras simples.",
                f"Öğrenci {topic} konusunu basit kelimelerle açıklayabilir.",
            ),
            qlp_txt(
                "The student can connect the idea to one real-life case.",
                "El estudiante puede conectar la idea con un caso de la vida real.",
                "Öğrenci fikri gerçek hayattan bir örnekle ilişkilendirebilir.",
            ),
        ],
        "warm_up": [
            qlp_txt(
                f"What do you observe about {topic}?",
                f"¿Qué observas sobre {topic}?",
                f"{topic} hakkında ne gözlemliyorsun?",
            ),
            qlp_txt(
                f"Where can we see {topic} in real life?",
                f"¿Dónde podemos ver {topic} en la vida real?",
                f"{topic} konusunu gerçek hayatta nerede görebiliriz?",
            ),
            qlp_txt(
                f"What do you think causes {topic}?",
                f"¿Qué crees que causa {topic}?",
                f"Sence {topic} neyin sonucu olarak ortaya çıkıyor?",
            ),
        ],
        "main_activity": [
            qlp_txt(
                "Start from observation and move to explanation.",
                "Empieza desde la observación y pasa a la explicación.",
                "Gözlemden başlayıp açıklamaya geçin.",
            ),
            qlp_txt(
                "Check understanding with why/how questions.",
                "Comprueba la comprensión con preguntas de por qué/cómo.",
                "Anlamayı neden/nasıl sorularıyla kontrol edin.",
            ),
        ],
        "core_examples": [
            material["concept_explanation"],
            material["real_life_application"],
        ],
        "guided_practice": [
            qlp_txt(
                "Ask the student to predict before explaining.",
                "Pide una predicción antes de explicar.",
                "Açıklamadan önce öğrenciden tahmin yapmasını isteyin.",
            ),
            qlp_txt(
                "Rebuild the explanation from one concrete example.",
                "Reconstruye la explicación a partir de un ejemplo concreto.",
                "Açıklamayı somut bir örnekten yola çıkarak yeniden kurun.",
            ),
        ],
        "practice_questions": [
            qlp_txt(f"What is {topic}?", f"¿Qué es {topic}?", f"{topic} nedir?"),
            qlp_txt(f"Why does {topic} happen?", f"¿Por qué ocurre {topic}?", f"{topic} neden olur?"),
            qlp_txt("What is one real-life example?", "¿Cuál es un ejemplo de la vida real?", "Gerçek hayattan bir örnek nedir?"),
            qlp_txt(
                "What would change if one condition changed?",
                "¿Qué cambiaría si una condición cambiara?",
                "Bir koşul değişseydi ne değişirdi?",
            ),
        ],
        "freer_task": [
            qlp_txt(
                f"Student explains {topic} in their own words.",
                f"El estudiante explica {topic} con sus propias palabras.",
                f"Öğrenci {topic} konusunu kendi sözleriyle açıklar.",
            ),
            qlp_txt(
                "Student adds one new example.",
                "El estudiante añade un ejemplo nuevo.",
                "Öğrenci yeni bir örnek ekler.",
            ),
        ],
        "wrap_up": [
            qlp_txt("Review the main explanation.", "Repasa la explicación principal.", "Ana açıklamayı gözden geçirin."),
            qlp_txt(
                "Ask one final check-for-understanding question.",
                "Haz una pregunta final de comprobación.",
                "Son bir anlama kontrolü sorusu sorun.",
            ),
        ],
        "teacher_moves": _teacher_move_block("science", purpose),
        "extension_task": qlp_txt(
            f"Ask the student to describe a second real-life case related to {topic}.",
            f"Pide al estudiante que describa un segundo caso de la vida real relacionado con {topic}.",
            f"Öğrenciden {topic} ile ilgili ikinci bir gerçek yaşam örneğini açıklamasını isteyin.",
        ),
        "homework": qlp_txt(
            f"Write 3 facts and 1 question about {topic}.",
            f"Escribe 3 hechos y 1 pregunta sobre {topic}.",
            f"{topic} hakkında 3 bilgi ve 1 soru yazın.",
        ),
        "reading_passage": "",
        "listening_script": "",
        "core_material": material,
    }


def _music_plan(stage: str, level: str, purpose: str, topic: str) -> dict:
    material = {
        "performance_goal": qlp_txt(
            f"Perform one short pattern or focused task related to {topic}.",
            f"Realizar un patrón corto o una tarea focalizada relacionada con {topic}.",
            f"{topic} ile ilgili kısa bir kalıbı ya da odaklı bir görevi uygulayın.",
        )
    }

    return {
        "title": f"{subject_label('music')}: {_capitalize_topic(topic)}",
        "objective": qlp_txt(
            f"Students will practice {topic} through demonstration, imitation, and short performance.",
            f"El estudiante practicará {topic} mediante demostración, imitación y una breve ejecución.",
            f"Öğrenciler {topic} konusunu gösterim, taklit ve kısa performans yoluyla çalışacaktır.",
        ),
        "recommended_level": level,
        "plan_language": get_plan_language(),
        "student_material_language": get_plan_language(),
        "success_criteria": [
            qlp_txt(
                f"The student can perform or repeat the key pattern from {topic}.",
                f"El estudiante puede ejecutar o repetir el patrón clave de {topic}.",
                f"Öğrenci {topic} içindeki temel kalıbı uygulayabilir ya da tekrar edebilir.",
            ),
            qlp_txt(
                "The student can describe one improvement from the practice.",
                "El estudiante puede describir una mejora tras la práctica.",
                "Öğrenci çalışmadan sonra bir gelişmeyi açıklayabilir.",
            ),
        ],
        "warm_up": [
            qlp_txt(
                f"What do you notice first about {topic}?",
                f"¿Qué notas primero sobre {topic}?",
                f"{topic} hakkında ilk neyi fark ediyorsun?",
            ),
            qlp_txt(
                f"Have you practiced {topic} before?",
                f"¿Has practicado {topic} antes?",
                f"Daha önce {topic} çalıştın mı?",
            ),
            qlp_txt(
                "What part may be difficult today?",
                "¿Qué parte puede ser difícil hoy?",
                "Bugün hangi kısım zor olabilir?",
            ),
        ],
        "main_activity": [
            qlp_txt(
                "Demonstrate first, then ask for imitation.",
                "Demuestra primero y luego pide imitación.",
                "Önce gösterin, sonra taklit etmesini isteyin.",
            ),
            qlp_txt(
                "Keep practice in short cycles.",
                "Mantén la práctica en ciclos cortos.",
                "Çalışmayı kısa döngüler hâlinde sürdürün.",
            ),
        ],
        "core_examples": [material["performance_goal"]],
        "guided_practice": [
            qlp_txt(
                "Repeat in short chunks with correction.",
                "Repite en fragmentos cortos con corrección.",
                "Düzeltmeyle birlikte kısa parçalar hâlinde tekrar edin.",
            ),
            qlp_txt(
                "Increase independence after each attempt.",
                "Aumenta la independencia después de cada intento.",
                "Her denemeden sonra bağımsızlığı artırın.",
            ),
        ],
        "practice_questions": [
            qlp_txt("What changed in the second attempt?", "¿Qué cambió en el segundo intento?", "İkinci denemede ne değişti?"),
            qlp_txt("What needs more control?", "¿Qué necesita más control?", "Neyin daha fazla kontrole ihtiyacı var?"),
            qlp_txt("What improved?", "¿Qué mejoró?", "Ne gelişti?"),
        ],
        "freer_task": [
            qlp_txt("Student performs with less support.", "El estudiante ejecuta con menos apoyo.", "Öğrenci daha az destekle uygular."),
            qlp_txt("Teacher asks for a short reflection.", "El profesor pide una reflexión breve.", "Öğretmen kısa bir yansıtma ister."),
        ],
        "wrap_up": [
            qlp_txt(
                "Review the musical focus of the lesson.",
                "Repasa el foco musical de la clase.",
                "Dersin müzikal odağını gözden geçirin.",
            ),
            qlp_txt(
                "End with one final repetition or mini performance.",
                "Termina con una repetición final o mini ejecución.",
                "Bir son tekrar ya da mini performansla bitirin.",
            ),
        ],
        "teacher_moves": _teacher_move_block("music", purpose),
        "extension_task": qlp_txt(
            f"Repeat the pattern again with one small variation related to {topic}.",
            f"Repite el patrón otra vez con una pequeña variación relacionada con {topic}.",
            f"Kalibi {topic} ile ilgili küçük bir değişiklikle tekrar edin.",
        ),
        "homework": qlp_txt(
            f"Practice {topic} for 5 minutes.",
            f"Practica {topic} durante 5 minutos.",
            f"{topic} konusunu 5 dakika çalışın.",
        ),
        "reading_passage": "",
        "listening_script": "",
        "core_material": material,
    }


def _study_skills_plan(stage: str, level: str, purpose: str, topic: str) -> dict:
    lang = get_plan_language()

    if lang == "tr":
        steps = [
            "1. Görevi adlandır.",
            "2. Görevi daha küçük parçalara ayır.",
            "3. İlk adımı belirle.",
            "4. Sonunda ilerlemeyi kontrol et.",
        ]
    elif lang == "es":
        steps = [
            "1. Nombra la tarea.",
            "2. Divídela en partes pequeñas.",
            "3. Decide la primera acción.",
            "4. Revisa el progreso al final.",
        ]
    else:
        steps = [
            "1. Name the task.",
            "2. Break it into smaller parts.",
            "3. Decide the first action.",
            "4. Check progress at the end.",
        ]

    return {
        "title": f"{subject_label('study_skills')}: {_capitalize_topic(topic)}",
        "objective": qlp_txt(
            f"Students will learn and apply a practical study strategy connected to {topic}.",
            f"El estudiante aprenderá y aplicará una estrategia de estudio práctica relacionada con {topic}.",
            f"Öğrenciler {topic} ile bağlantılı pratik bir çalışma stratejisini öğrenecek ve uygulayacak.",
        ),
        "recommended_level": level,
        "plan_language": get_plan_language(),
        "student_material_language": get_plan_language(),
        "success_criteria": [
            qlp_txt(
                "The student can explain the strategy clearly.",
                "El estudiante puede explicar la estrategia con claridad.",
                "Öğrenci stratejiyi açıkça açıklayabilir.",
            ),
            qlp_txt(
                "The student can apply the strategy to a real task.",
                "El estudiante puede aplicar la estrategia a una tarea real.",
                "Öğrenci stratejiyi gerçek bir göreve uygulayabilir.",
            ),
        ],
        "warm_up": [
            qlp_txt(
                f"What usually feels difficult about {topic}?",
                f"¿Qué suele sentirse difícil en {topic}?",
                f"{topic} konusunda genellikle hangi şey zor geliyor?",
            ),
            qlp_txt(
                "What distracts you when you study?",
                "¿Qué te distrae cuando estudias?",
                "Çalışırken dikkatini ne dağıtıyor?",
            ),
            qlp_txt(
                "What helps you focus?",
                "¿Qué te ayuda a concentrarte?",
                "Odaklanmana ne yardımcı oluyor?",
            ),
        ],
        "main_activity": [
            qlp_txt(
                "Introduce one practical strategy.",
                "Presenta una estrategia práctica.",
                "Bir pratik strateji tanıtın.",
            ),
            qlp_txt(
                "Model the strategy with a real school task.",
                "Modela la estrategia con una tarea escolar real.",
                "Stratejiyi gerçek bir okul göreviyle modelleyin.",
            ),
        ],
        "core_examples": [
            qlp_txt(
                "Strategy name: 10-minute planning routine.",
                "Nombre de la estrategia: rutina de planificación de 10 minutos.",
                "Stratejinin adı: 10 dakikalık planlama rutini.",
            ),
        ],
        "guided_practice": [
            qlp_txt(
                "Student tries the strategy on a small real task.",
                "El estudiante prueba la estrategia en una tarea real pequeña.",
                "Öğrenci stratejiyi küçük bir gerçek görev üzerinde dener.",
            ),
            qlp_txt(
                "Teacher helps adapt the strategy to the student’s reality.",
                "El profesor ayuda a adaptar la estrategia a la realidad del estudiante.",
                "Öğretmen stratejinin öğrencinin gerçekliğine uyarlanmasına yardımcı olur.",
            ),
        ],
        "practice_questions": [
            qlp_txt("Which step seems most useful?", "¿Qué paso parece más útil?", "Hangi adım en yararlı görünüyor?"),
            qlp_txt("What usually blocks you?", "¿Qué suele bloquearte?", "Seni genellikle ne engelliyor?"),
            qlp_txt("How will you use this tomorrow?", "¿Cómo vas a usar esto mañana?", "Bunu yarın nasıl kullanacaksın?"),
        ],
        "freer_task": [
            qlp_txt(
                "Student applies the strategy independently.",
                "El estudiante aplica la estrategia de forma independiente.",
                "Öğrenci stratejiyi bağımsız olarak uygular.",
            ),
            qlp_txt(
                "Student decides where to use it this week.",
                "El estudiante decide dónde usarla esta semana.",
                "Öğrenci bu hafta bunu nerede kullanacağına karar verir.",
            ),
        ],
        "wrap_up": [
            qlp_txt(
                "Review the steps of the strategy.",
                "Repasa los pasos de la estrategia.",
                "Stratejinin adımlarını gözden geçirin.",
            ),
            qlp_txt(
                "Ask the student to name one real use for it.",
                "Pide al estudiante que nombre un uso real para ella.",
                "Öğrenciden bunun için gerçek bir kullanım örneği vermesini isteyin.",
            ),
        ],
        "teacher_moves": _teacher_move_block("study_skills", purpose),
        "extension_task": qlp_txt(
            "Ask the student to adapt the strategy to a second subject.",
            "Pide al estudiante que adapte la estrategia a una segunda materia.",
            "Öğrenciden stratejiyi ikinci bir derse uyarlamasını isteyin.",
        ),
        "homework": qlp_txt(
            f"Use the strategy once this week while working on {topic}.",
            f"Usa la estrategia una vez esta semana mientras trabajas en {topic}.",
            f"Bu hafta {topic} üzerinde çalışırken stratejiyi bir kez kullanın.",
        ),
        "reading_passage": "",
        "listening_script": "",
        "core_material": {"strategy_steps": steps},
    }


def _general_plan(stage: str, level: str, purpose: str, topic: str) -> dict:
    return {
        "title": f"{_capitalize_topic(topic)}",
        "objective": qlp_txt(
            f"Students will explore and develop understanding of {topic}.",
            f"El estudiante explorará y desarrollará comprensión sobre {topic}.",
            f"Öğrenciler {topic} konusunu keşfedecek ve anlayış geliştirecek.",
        ),
        "recommended_level": level,
        "plan_language": get_plan_language(),
        "student_material_language": get_plan_language(),
        "success_criteria": [
            qlp_txt(
                f"The student can explain the main idea of {topic}.",
                f"El estudiante puede explicar la idea principal de {topic}.",
                f"Öğrenci {topic} konusunun ana fikrini açıklayabilir.",
            ),
            qlp_txt(
                "The student can give at least one practical example.",
                "El estudiante puede dar al menos un ejemplo práctico.",
                "Öğrenci en az bir pratik örnek verebilir.",
            ),
        ],
        "warm_up": [
            qlp_txt(
                f"What do you already know about {topic}?",
                f"¿Qué sabes ya sobre {topic}?",
                f"{topic} hakkında zaten ne biliyorsun?",
            ),
            qlp_txt(
                f"Where have you encountered {topic} before?",
                f"¿Dónde has encontrado {topic} antes?",
                f"{topic} ile daha önce nerede karşılaştın?",
            ),
        ],
        "main_activity": [
            qlp_txt(
                f"Introduce the key concept of {topic}.",
                f"Presenta el concepto clave de {topic}.",
                f"{topic} konusunun temel kavramını tanıtın.",
            ),
            qlp_txt(
                "Work through one example together.",
                "Trabaja un ejemplo juntos.",
                "Bir örneği birlikte yapın.",
            ),
        ],
        "core_examples": [
            qlp_txt(
                f"Give one clear example that illustrates {topic}.",
                f"Da un ejemplo claro que ilustre {topic}.",
                f"{topic} konusunu açıklayan net bir örnek verin.",
            ),
        ],
        "guided_practice": [
            qlp_txt(
                "Guide the student through one task.",
                "Guía al estudiante en una tarea.",
                "Öğrenciyi bir görev boyunca yönlendirin.",
            ),
            qlp_txt(
                "Ask for explanation at each step.",
                "Pide la explicación en cada paso.",
                "Her adımda açıklama isteyin.",
            ),
        ],
        "practice_questions": [
            qlp_txt(f"What is {topic}?", f"¿Qué es {topic}?", f"{topic} nedir?"),
            qlp_txt("Can you give an example?", "¿Puedes dar un ejemplo?", "Bir örnek verebilir misin?"),
            qlp_txt("Where can you apply this?", "¿Dónde puedes aplicar esto?", "Bunu nerede uygulayabilirsin?"),
        ],
        "freer_task": [
            qlp_txt(
                "Student applies or explains the concept independently.",
                "El estudiante aplica o explica el concepto de forma independiente.",
                "Öğrenci kavramı bağımsız olarak uygular ya da açıklar.",
            ),
        ],
        "wrap_up": [
            qlp_txt(
                "Review the key idea from the lesson.",
                "Repasa la idea clave de la clase.",
                "Dersteki ana fikri gözden geçirin.",
            ),
            qlp_txt(
                "Ask one final check question.",
                "Haz una pregunta final de comprobación.",
                "Son bir kontrol sorusu sorun.",
            ),
        ],
        "teacher_moves": _teacher_move_block("study_skills", purpose),
        "extension_task": qlp_txt(
            f"Research one more aspect of {topic} and share it next lesson.",
            f"Investiga un aspecto más de {topic} y compártelo en la próxima clase.",
            f"{topic} ile ilgili bir yönü daha araştırın ve bunu sonraki derste paylaşın.",
        ),
        "homework": qlp_txt(
            f"Review today's work on {topic}.",
            f"Repasa el trabajo de hoy sobre {topic}.",
            f"Bugün {topic} üzerine yapılan çalışmayı gözden geçirin.",
        ),
        "reading_passage": "",
        "listening_script": "",
        "core_material": {},
    }


def build_quick_lesson_plan(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    lesson_purpose: str,
    topic: str,
) -> dict:
    engine = get_subject_engine(subject)

    if engine == "language":
        return _language_plan(subject, learner_stage, level_or_band, lesson_purpose, topic)
    if engine == "math":
        return _math_plan(learner_stage, level_or_band, lesson_purpose, topic)
    if engine == "science":
        return _science_plan(learner_stage, level_or_band, lesson_purpose, topic)
    if engine == "music":
        return _music_plan(learner_stage, level_or_band, lesson_purpose, topic)
    if engine == "study_skills":
        return _study_skills_plan(learner_stage, level_or_band, lesson_purpose, topic)

    return _general_plan(learner_stage, level_or_band, lesson_purpose, topic)


def normalize_planner_output(plan: dict) -> dict:
    plan = dict(plan or {})

    defaults = {
        "title": "",
        "objective": "",
        "recommended_level": "",
        "plan_language": get_plan_language(),
        "student_material_language": get_plan_language(),
        "success_criteria": [],
        "warm_up": [],
        "main_activity": [],
        "core_examples": [],
        "guided_practice": [],
        "practice_questions": [],
        "freer_task": [],
        "wrap_up": [],
        "teacher_moves": [],
        "extension_task": "",
        "homework": "",
        "reading_passage": "",
        "listening_script": "",
        "core_material": {},
    }

    out = {}
    for k, v in defaults.items():
        out[k] = plan.get(k, v)

    if not isinstance(out["core_material"], dict):
        out["core_material"] = {}

    _cm_keys = [
        "gist_questions",
        "detail_questions",
        "pre_task_questions",
        "target_vocabulary",
        "post_task",
    ]
    for _ck in _cm_keys:
        if _ck in out and _ck not in out["core_material"]:
            out["core_material"][_ck] = out.pop(_ck)

    list_keys = [
        "success_criteria",
        "warm_up",
        "main_activity",
        "core_examples",
        "guided_practice",
        "practice_questions",
        "freer_task",
        "wrap_up",
        "teacher_moves",
    ]
    for k in list_keys:
        if not isinstance(out.get(k), list):
            out[k] = [] if out.get(k) in (None, "") else [str(out.get(k))]

    out["title"] = _clean_display_text(out.get("title", ""))
    if "core_material" not in out or not isinstance(out["core_material"], dict):
        out["core_material"] = {}

    if "topic" in out:
        out["topic"] = _clean_display_text(out.get("topic", ""))

    return out


def get_ai_provider() -> str:
    provider = ""
    try:
        provider = str(st.secrets.get("AI_PROVIDER", "")).strip().lower()
    except Exception:
        provider = ""

    if not provider:
        provider = str(os.getenv("AI_PROVIDER", "")).strip().lower()

    if provider not in {"gemini", "openrouter"}:
        provider = "gemini"

    return provider


def get_ai_model() -> str:
    provider = get_ai_provider()

    model = ""
    try:
        model = str(st.secrets.get("AI_MODEL", "")).strip()
    except Exception:
        model = ""

    if not model:
        model = str(os.getenv("AI_MODEL", "")).strip()

    if model:
        return model

    if provider == "gemini":
        return "gemini-2.5-flash"

    return "openrouter/free"


def get_default_model_for_provider(provider: str) -> str:
    p = str(provider or "").strip().lower()
    if p == "gemini":
        return "gemini-2.5-flash"
    return "openrouter/free"


def get_ai_model_for_provider(provider: str) -> str:
    custom_model = ""
    try:
        custom_model = str(st.secrets.get("AI_MODEL", "")).strip()
    except Exception:
        custom_model = ""

    if not custom_model:
        custom_model = str(os.getenv("AI_MODEL", "")).strip()

    if custom_model:
        return custom_model

    return get_default_model_for_provider(provider)


def _extract_json_object_from_text(text: str) -> dict:
    s = str(text or "").strip()

    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)

    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("AI response did not contain a valid JSON object.")

    json_text = s[start:end + 1]
    return json.loads(json_text)


def _build_ai_prompts(prompt_payload: dict) -> tuple[str, str]:
    system_prompt = (
        "You are an expert private lesson planner. "
        "Return exactly one valid JSON object and nothing else. "
        "Do not use markdown. Do not use code fences. "
        "All list fields must be arrays of strings. "
        "The core_material field must be a JSON object. "
        "Use the requested plan_language for teacher-facing sections. "
        "Use the requested student_material_language for reading_passage, listening_script, "
        "target_vocabulary, and comprehension questions whenever appropriate. "
        "IMPORTANT: Never use the English JSON key names (like gist_questions, detail_questions, "
        "core_material, pre_task_questions, etc.) as labels or headings inside text content. "
        "Write all text content in the requested plan_language. "
        "IMPORTANT: plan_language may be en, es, or tr. "
        "If plan_language is tr, write teacher-facing content in Turkish. "
        "If student_material_language is tr, write student-facing material in Turkish."
    )

    user_prompt = f"""
Create one complete lesson plan as JSON.

Planner input:
{json.dumps(prompt_payload, ensure_ascii=False, indent=2)}

Rules:
- Return JSON only.
- Include all required_sections.
- Use empty string "" or empty list [] if a section is not needed.
- success_criteria must be a list of strings.
- warm_up, main_activity, core_examples, guided_practice, practice_questions, freer_task, wrap_up, teacher_moves must be lists of strings.
- extension_task and homework must be strings.
- core_material must be an object.
- If the lesson is reading-focused, include a reading_passage.
- If the lesson is listening-focused, include a listening_script.
- Keep the lesson practical for one 45-minute private lesson.
- The JSON must match the current planner structure exactly.
"""
    return system_prompt, user_prompt


def _generate_with_openrouter(system_prompt: str, user_prompt: str) -> str:
    api_key = ""
    try:
        api_key = str(st.secrets.get("OPENROUTER_API_KEY", "")).strip()
    except Exception:
        api_key = ""

    if not api_key:
        api_key = str(os.getenv("OPENROUTER_API_KEY", "")).strip()

    if not api_key:
        raise RuntimeError(t("missing_openrouter_api_key"))

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    response = client.chat.completions.create(
        model=get_ai_model_for_provider("openrouter"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
    )

    raw_text = str(response.choices[0].message.content or "").strip()
    if not raw_text:
        raise ValueError(t("empty_ai_response"))

    return raw_text


def _generate_with_gemini(system_prompt: str, user_prompt: str) -> str:
    from google import genai

    api_key = ""
    try:
        api_key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:
        api_key = ""

    if not api_key:
        api_key = str(os.getenv("GEMINI_API_KEY", "")).strip()

    if not api_key:
        raise RuntimeError(t("missing_gemini_api_key"))

    client = genai.Client(api_key=api_key)
    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    response = client.models.generate_content(
        model=get_ai_model_for_provider("gemini"),
        contents=full_prompt,
    )

    raw_text = str(getattr(response, "text", "") or "").strip()
    if not raw_text:
        raise ValueError(t("empty_gemini_response"))

    return raw_text


def generate_ai_lesson_plan(
    subject: str,
    learner_stage: str,
    level_or_band: str,
    lesson_purpose: str,
    topic: str,
    plan_language: str,
    student_material_language: str,
) -> dict:
    prompt_payload = {
        "subject": subject,
        "topic": topic,
        "learner_stage": learner_stage,
        "level_or_band": level_or_band,
        "lesson_purpose": lesson_purpose,
        "plan_language": plan_language,
        "student_material_language": student_material_language,
        "required_sections": [
            "title",
            "objective",
            "recommended_level",
            "plan_language",
            "student_material_language",
            "success_criteria",
            "warm_up",
            "main_activity",
            "core_examples",
            "guided_practice",
            "practice_questions",
            "freer_task",
            "wrap_up",
            "teacher_moves",
            "extension_task",
            "homework",
            "reading_passage",
            "listening_script",
            "core_material",
        ],
        "core_material_required_keys": [
            "target_vocabulary",
            "pre_task_questions",
            "gist_questions",
            "detail_questions",
            "post_task",
        ],
    }

    system_prompt, user_prompt = _build_ai_prompts(prompt_payload)
    provider = get_ai_provider()

    if provider == "gemini":
        provider_order = ["gemini", "openrouter"]
    else:
        provider_order = ["openrouter", "gemini"]

    errors = []

    for p in provider_order:
        try:
            if p == "gemini":
                raw_text = _generate_with_gemini(system_prompt, user_prompt)
            else:
                raw_text = _generate_with_openrouter(system_prompt, user_prompt)

            parsed = _extract_json_object_from_text(raw_text)
            return normalize_planner_output(parsed)

        except Exception as e:
            errors.append(f"{p}: {e}")

    raise RuntimeError(" | ".join(errors))


AI_DAILY_LIMIT = 3
AI_COOLDOWN_SECONDS = 10


def generate_quick_lesson_plan_with_fallback(
    mode: str,
    subject: str,
    learner_stage: str,
    level_or_band: str,
    lesson_purpose: str,
    topic: str,
) -> tuple[dict, str, Optional[str]]:
    """
    Returns: (plan, resolved_mode, warning_message)
    resolved_mode is 'ai' or 'template'
    """

    template_plan = normalize_planner_output(
        build_quick_lesson_plan(
            subject=subject,
            learner_stage=learner_stage,
            level_or_band=level_or_band,
            lesson_purpose=lesson_purpose,
            topic=topic,
        )
    )

    if str(mode).strip().lower() != "ai":
        return template_plan, "template", None

    from helpers.planner_storage import get_ai_planner_usage_status, log_ai_usage
    usage = get_ai_planner_usage_status()

    if usage["used_today"] >= AI_DAILY_LIMIT:
        return template_plan, "template", t("ai_limit_reached")

    if not usage["cooldown_ok"]:
        return template_plan, "template", t(
            "ai_cooldown_active",
            seconds=usage["seconds_left"]
        )

    try:
        log_ai_usage(
            request_kind="quick_lesson_ai",
            status="requested",
            meta={
                "subject": subject,
                "topic": topic,
                "lesson_purpose": lesson_purpose,
            },
        )

        ai_plan = generate_ai_lesson_plan(
            subject=subject,
            learner_stage=learner_stage,
            level_or_band=level_or_band,
            lesson_purpose=lesson_purpose,
            topic=topic,
            plan_language=get_plan_language(),
            student_material_language=get_student_material_language(subject),
        )

        ai_plan = normalize_planner_output(ai_plan)

        log_ai_usage(
            request_kind="quick_lesson_ai",
            status="success",
            meta={
                "subject": subject,
                "topic": topic,
                "lesson_purpose": lesson_purpose,
            },
        )

        return ai_plan, "ai", None

    except Exception as e:
        log_ai_usage(
            request_kind="quick_lesson_ai",
            status="failed",
            meta={
                "subject": subject,
                "topic": topic,
                "lesson_purpose": lesson_purpose,
                "error": str(e),
            },
        )
        return template_plan, "template", f"{t('ai_unavailable_fallback')} ({str(e)})"


def reset_quick_lesson_planner_state() -> None:
    keys_to_clear = [
        "quick_lesson_plan_result",
        "quick_lesson_plan_kept",
        "quick_lesson_plan_mode_used",
        "quick_lesson_plan_warning",
        "quick_lesson_no_template",
        "quick_plan_mode",
        "quick_plan_subject",
        "quick_plan_stage",
        "quick_plan_level",
        "quick_plan_purpose",
        "quick_plan_topic",
    ]
    for k in keys_to_clear:
        st.session_state.pop(k, None)
