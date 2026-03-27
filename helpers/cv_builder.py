import json, os, re
from typing import Optional
from core.i18n import t
# -----------------------------------------------------------------------
# CV BUILDER — template + AI generation
# Reuses the same AI infrastructure as helpers/lesson_planner.py
# -----------------------------------------------------------------------

AI_CV_DAILY_LIMIT = 3
AI_CV_COOLDOWN_SECONDS = 30


def _lp():
    """Lazy import to avoid circular dependency."""
    import helpers.lesson_planner as lp
    return lp


def _call_ai(system_prompt: str, user_prompt: str) -> str:
    """Route through the same provider chain used by the lesson planner."""
    lp = _lp()
    provider = lp.get_ai_provider()
    if provider == "gemini":
        order = ["gemini", "openrouter"]
    else:
        order = ["openrouter", "gemini"]

    errors = []
    for p in order:
        try:
            if p == "gemini":
                return lp._generate_with_gemini(system_prompt, user_prompt)
            else:
                return lp._generate_with_openrouter(system_prompt, user_prompt)
        except Exception as e:
            errors.append(f"{p}: {e}")

    raise RuntimeError(" | ".join(errors))


def _stage_label(stage: str) -> str:
    labels = {
        "early_primary": t("stage_early_primary"),
        "upper_primary": t("stage_upper_primary"),
        "lower_secondary": t("stage_lower_secondary"),
        "upper_secondary": t("stage_upper_secondary"),
        "adult_stage": t("stage_adult"),        
    }
    return labels.get(str(stage), str(stage))


def _lang_label(code: str) -> str:
    labels = {
        "en": t("english"),
        "es": t("spanish"),
        "tr": t("turkish"),
    }
    return labels.get(str(code).strip().lower(), str(code))


def _parse_lines(text: str) -> list:
    return [l.strip() for l in str(text or "").strip().splitlines() if l.strip()]


def _parse_csv(text: str) -> list:
    return [x.strip() for x in str(text or "").replace("\n", ",").split(",") if x.strip()]


# -----------------------------------------------------------------------
# TEMPLATE CV
# -----------------------------------------------------------------------

def build_template_cv(
    full_name: str,
    email: str,
    phone: str,
    location: str,
    date_of_birth: str,
    sex: str,
    subjects: list,
    teaching_stages: list,
    teaching_languages: list,
    professional_summary: str,
    education_text: str,
    certifications_text: str,
    experience_text: str,
    skills_text: str,
    availability: str,
    rate: str,
    role: str = "teacher",
    avatar_url: str = "",
) -> dict:
    stage_labels = [_stage_label(s) for s in (teaching_stages or [])]
    lang_labels  = [_lang_label(l) for l in (teaching_languages or [])]

    if not str(professional_summary or "").strip():
        subject_str = ", ".join(subjects) if subjects else t("cv_default_subjects")
        role_label = t("teacher_role") if str(role).strip().lower() == "teacher" else t("tutor_role")
        professional_summary = t(
            "cv_default_summary",
            role=role_label.lower(),
            subjects=subject_str,
            stages=", ".join(stage_labels) if stage_labels else t("cv_default_age_groups"),
        )

    return {
        "title": f"{t('cv')} \u2013 {full_name}" if full_name else t("my_cv"),
        "full_name": str(full_name or "").strip(),
        "email": str(email or "").strip(),
        "phone": str(phone or "").strip(),
        "location": str(location or "").strip(),
        "date_of_birth": str(date_of_birth or "").strip(),
        "sex": str(sex or "").strip(),
        "role": str(role or t("teacher_role")).strip().title(),
        "professional_summary": str(professional_summary or "").strip(),
        "subjects": list(subjects or []),
        "teaching_stages": stage_labels,
        "teaching_languages": lang_labels,
        "education": _parse_lines(education_text),
        "certifications": _parse_csv(certifications_text),
        "experience": _parse_lines(experience_text),
        "skills": _parse_csv(skills_text),
        "availability": str(availability or "").strip(),
        "rate": str(rate or "").strip(),
        "source_type": "template",
        "avatar_url": str(avatar_url or "").strip(),
    }


# -----------------------------------------------------------------------
# AI CV
# -----------------------------------------------------------------------

_CV_JSON_SCHEMA = """{
  "title": "CV – Full Name",
  "full_name": "string",
  "email": "string",
  "phone": "string",
  "location": "string",
  "date_of_birth": "string",
  "sex": "string",
  "role": "string",
  "professional_summary": "3-4 compelling sentences",
  "subjects": ["string"],
  "teaching_stages": ["string"],
  "teaching_languages": ["string"],
  "education": ["one entry per item, e.g. 'BA English – University of X, 2015'"],
  "certifications": ["string"],
  "experience": ["one entry per item, e.g. 'Private English Tutor – Self-employed, 2019–present: …'"],
  "skills": ["string"],
  "availability": "string",
  "rate": "string",
  "source_type": "ai"
}"""

_CV_SYSTEM_PROMPT = (
    "You are a professional CV writer specialising in teachers and private tutors.\n"
    "Generate a complete, polished CV in valid JSON using exactly this structure:\n"
    + _CV_JSON_SCHEMA
    + "\nReturn ONLY valid JSON. No markdown, no code fences, no explanation."
)


def build_ai_cv(
    full_name: str,
    email: str,
    phone: str,
    location: str,
    date_of_birth: str,
    sex: str,
    subjects: list,
    teaching_stages: list,
    teaching_languages: list,
    professional_summary: str,
    education_text: str,
    certifications_text: str,
    experience_text: str,
    skills_text: str,
    availability: str,
    rate: str,
    role: str,
    user_prompt: str,
    avatar_url: str = "",
) -> dict:
    stage_labels = [_stage_label(s) for s in (teaching_stages or [])]
    lang_labels  = [_lang_label(l) for l in (teaching_languages or [])]

    user_msg = f"""Profile data:
- Full name: {full_name}
- Email: {email}
- Phone: {phone}
- Location: {location}
- Date of birth: {date_of_birth}
- Sex: {sex}
- Role: {role}
- Subjects: {', '.join(subjects) or 'various'}
- Teaching stages: {', '.join(stage_labels) or 'various'}
- Teaching languages: {', '.join(lang_labels) or 'various'}
- Current summary: {professional_summary or 'N/A'}
- Education: {education_text or 'N/A'}
- Certifications: {certifications_text or 'N/A'}
- Experience: {experience_text or 'N/A'}
- Skills: {skills_text or 'N/A'}
- Availability: {availability or 'N/A'}
- Rate: {rate or 'N/A'}

User customisation / instructions:
{user_prompt or 'Create a professional, polished teacher/tutor CV.'}"""

    raw = _call_ai(_CV_SYSTEM_PROMPT, user_msg)

    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        cv = json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            cv = json.loads(m.group())
        else:
            raise ValueError(f"Could not parse AI CV response as JSON. Preview: {raw[:300]}")

    cv["source_type"] = "ai"
    cv["avatar_url"] = str(avatar_url or "").strip()
    return cv


# -----------------------------------------------------------------------
# AI COVER LETTER
# -----------------------------------------------------------------------

_CL_SYSTEM_PROMPT = (
    "You are a professional cover letter writer for teachers and private tutors.\n"
    "Write a compelling, personalised cover letter in plain text only.\n"
    "No markdown, no headers, no bullet points.\n"
    "Format: opening paragraph, 2–3 body paragraphs, closing paragraph, sign-off.\n"
    "Maximum 380 words."
)


def build_ai_cover_letter(cv: dict, user_prompt: str) -> str:
    full_name    = str(cv.get("full_name") or "").strip()
    email        = str(cv.get("email") or "").strip()
    role         = str(cv.get("role") or "Teacher").strip()
    subjects     = cv.get("subjects") or []
    stages       = cv.get("teaching_stages") or []
    summary      = str(cv.get("professional_summary") or "").strip()
    experience   = cv.get("experience") or []
    certs        = cv.get("certifications") or []

    user_msg = f"""Candidate:
- Name: {full_name}
- Email: {email}
- Role: {role}
- Subjects: {', '.join(subjects) if subjects else 'various'}
- Teaching stages: {', '.join(stages) if stages else 'various'}
- Summary: {summary}
- Experience highlights: {'; '.join(experience[:3]) if experience else 'N/A'}
- Certifications: {', '.join(certs) if certs else 'N/A'}

Cover letter instructions:
{user_prompt or 'Write a strong general cover letter for private tutoring opportunities.'}

Write the complete cover letter text only."""

    return _call_ai(_CL_SYSTEM_PROMPT, user_msg)


# -----------------------------------------------------------------------
# PDF IMPORT — extract CV data from raw PDF text via AI
# -----------------------------------------------------------------------

_IMPORT_SYSTEM_PROMPT = (
    "You are a CV parsing assistant.\n"
    "Given raw text extracted from a teacher/tutor CV PDF, extract all available information "
    "and return it as valid JSON with exactly this structure (omit or use empty string/list for missing fields):\n"
    '{\n'
    '  "full_name": "string",\n'
    '  "email": "string",\n'
    '  "phone": "string",\n'
    '  "location": "string",\n'
    '  "date_of_birth": "YYYY-MM-DD or empty string",\n'
    '  "sex": "Male|Female|Other|Prefer not to say|empty string",\n'
    '  "role": "teacher|tutor",\n'
    '  "professional_summary": "string",\n'
    '  "subjects": ["string"],\n'
    '  "teaching_stages": ["early_primary|upper_primary|lower_secondary|upper_secondary|adult_stage"],\n'
    '  "teaching_languages": ["en|es"],\n'
    '  "education": ["one entry per item"],\n'
    '  "certifications": ["string"],\n'
    '  "experience": ["one entry per item"],\n'
    '  "skills": ["string"],\n'
    '  "availability": "string",\n'
    '  "rate": "string"\n'
    '}\n'
    "Return ONLY valid JSON. No markdown, no code fences, no explanation."
)


def extract_cv_from_pdf_text(pdf_text: str) -> dict:
    """Send raw PDF text to AI and get back a structured CV dict."""
    user_msg = f"Extract all CV information from the following text:\n\n{pdf_text[:6000]}"
    raw = _call_ai(_IMPORT_SYSTEM_PROMPT, user_msg)
    raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        return json.loads(raw)
    except Exception:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise ValueError(f"Could not parse AI CV import response. Preview: {raw[:300]}")
