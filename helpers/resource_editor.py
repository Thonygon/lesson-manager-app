from __future__ import annotations

import copy
import json
import logging
from typing import Any, Callable

import streamlit as st

from core.i18n import t


logger = logging.getLogger(__name__)

_SKIP_KEYS = {
    "visual_support",
    "visual_supports",
    "_visual_support_status",
    "cover_image",
    "avatar_url",
    "image_url",
    "image",
}


def _label(key: str, fallback: str) -> str:
    value = t(key)
    return value if value and value != key else fallback


def _path_label(path: tuple[Any, ...]) -> str:
    return " > ".join(str(part + 1 if isinstance(part, int) else part).replace("_", " ") for part in path)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _collect_editable_fields(value: Any, path: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    if path and str(path[-1]).strip() in _SKIP_KEYS:
        return []
    fields: list[dict[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            fields.extend(_collect_editable_fields(item, path + (key,)))
        return fields
    if isinstance(value, list):
        if all(_is_scalar(item) for item in value):
            fields.append({"path": path, "kind": "list", "value": "\n".join(str(item) for item in value if str(item).strip())})
            return fields
        for idx, item in enumerate(value):
            fields.extend(_collect_editable_fields(item, path + (idx,)))
        return fields
    if _is_scalar(value):
        fields.append({"path": path, "kind": "scalar", "value": "" if value is None else str(value), "original": value})
    return fields


def _get_container(root: Any, path: tuple[Any, ...]) -> Any:
    current = root
    for part in path[:-1]:
        current = current[part]
    return current


def _coerce_scalar(value: str, original: Any) -> Any:
    if isinstance(original, bool):
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
    if isinstance(original, int) and not isinstance(original, bool):
        try:
            return int(str(value).strip())
        except Exception:
            return original
    if isinstance(original, float):
        try:
            return float(str(value).strip())
        except Exception:
            return original
    if original is None and not str(value).strip():
        return None
    return str(value)


def _set_field_value(root: Any, field: dict[str, Any], raw_value: str) -> None:
    path = tuple(field.get("path") or ())
    if not path:
        return
    parent = _get_container(root, path)
    key = path[-1]
    if field.get("kind") == "list":
        value = [line.strip() for line in str(raw_value or "").splitlines() if line.strip()]
    else:
        value = _coerce_scalar(str(raw_value or ""), field.get("original"))
    parent[key] = value


def _build_payload_from_fields(payload: dict, fields: list[dict[str, Any]], action_key_prefix: str) -> dict:
    updated = copy.deepcopy(payload or {})
    for idx, field in enumerate(fields):
        _set_field_value(updated, field, st.session_state.get(f"{action_key_prefix}_field_{idx}", ""))
    return updated


def _field_prompt_items(fields: list[dict[str, Any]], action_key_prefix: str) -> list[dict[str, str]]:
    high_priority_terms = ("answer", "answer key", "answer_key", "answers")
    medium_priority_terms = ("question", "instruction", "title", "summary", "objective", "text", "notes")
    ranked = []
    for idx, field in enumerate(fields):
        label = _path_label(tuple(field.get("path") or ()))
        value = str(st.session_state.get(f"{action_key_prefix}_field_{idx}", field.get("value", "")) or "")
        label_norm = label.casefold()
        if any(term in label_norm for term in high_priority_terms):
            score = 3
        elif any(term in label_norm for term in medium_priority_terms):
            score = 2
        else:
            score = 1
        ranked.append((score, idx, label, value))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    items: list[dict[str, str]] = []
    char_budget = 14000
    used = 0
    for _score, idx, label, value in ranked:
        clipped = value[:700]
        entry_size = len(label) + len(clipped)
        if items and used + entry_size > char_budget:
            continue
        items.append({"id": f"f{idx}", "path": label, "value": clipped})
        used += entry_size
    return sorted(items, key=lambda item: int(item["id"][1:]))


def _get_by_path(root: Any, path: tuple[Any, ...]) -> Any:
    current = root
    for part in path:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and isinstance(part, int) and 0 <= part < len(current):
            current = current[part]
        else:
            return None
    return current


def _updates_from_parsed_response(parsed: Any, fields: list[dict[str, Any]]) -> dict[str, str]:
    valid_ids = {f"f{idx}" for idx, _field in enumerate(fields)}
    cleaned: dict[str, str] = {}

    if isinstance(parsed, dict):
        updates = parsed.get("updates")
        if isinstance(updates, dict):
            updates = [{"id": key, "value": value} for key, value in updates.items()]
        if isinstance(updates, list):
            for update in updates:
                if not isinstance(update, dict):
                    continue
                field_id = str(update.get("id") or update.get("field_id") or "").strip()
                if not field_id and update.get("path"):
                    path_label = str(update.get("path") or "").strip().casefold()
                    for idx, field in enumerate(fields):
                        if _path_label(tuple(field.get("path") or ())).casefold() == path_label:
                            field_id = f"f{idx}"
                            break
                if field_id in valid_ids:
                    cleaned[field_id] = str(update.get("value") or update.get("text") or "")
            if cleaned:
                return cleaned

        for key, value in parsed.items():
            field_id = str(key or "").strip()
            if field_id in valid_ids:
                cleaned[field_id] = str(value or "")
        if cleaned:
            return cleaned

        for idx, field in enumerate(fields):
            value = _get_by_path(parsed, tuple(field.get("path") or ()))
            if value is None:
                continue
            if isinstance(value, list):
                cleaned[f"f{idx}"] = "\n".join(str(item) for item in value if str(item).strip())
            elif _is_scalar(value):
                cleaned[f"f{idx}"] = str(value)
        return cleaned

    if isinstance(parsed, list):
        return _updates_from_parsed_response({"updates": parsed}, fields)

    return {}


def _parse_ai_json(raw: str) -> Any:
    import helpers.lesson_planner as lp

    try:
        return lp._extract_json_object_from_text(raw)
    except Exception:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        text = text.replace("\ufeff", "")
        text = json.dumps(json.loads(text))
        return json.loads(text)


def _wants_answer_key_fix(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    return any(term in text for term in ("answer", "answers", "answer key", "answerkey", "clave", "respuestas"))


def _wants_structural_refine(prompt: str) -> bool:
    text = str(prompt or "").casefold()
    structural_terms = (
        "add",
        "increase",
        "more question",
        "more questions",
        "extra question",
        "remove",
        "delete",
        "replace",
        "change part",
        "change section",
        "part 1",
        "part 2",
        "part 3",
        "section 1",
        "section 2",
        "section 3",
        "reading passage",
        "passage",
        "number of questions",
        "aumenta",
        "agrega",
        "añade",
        "cambia",
        "elimina",
        "parte",
        "sección",
        "metin",
        "bölüm",
    )
    return any(term in text for term in structural_terms)


def _strip_noneditable_keys(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_noneditable_keys(item)
            for key, item in value.items()
            if str(key).strip() not in _SKIP_KEYS
        }
    if isinstance(value, list):
        return [_strip_noneditable_keys(item) for item in value]
    return value


def _restore_noneditable_keys(original: Any, updated: Any) -> Any:
    if isinstance(original, dict) and isinstance(updated, dict):
        merged = dict(updated)
        for key, original_value in original.items():
            if str(key).strip() in _SKIP_KEYS:
                merged[key] = original_value
            elif key in merged:
                merged[key] = _restore_noneditable_keys(original_value, merged[key])
        return merged
    if isinstance(original, list) and isinstance(updated, list):
        restored = []
        for idx, item in enumerate(updated):
            if idx < len(original):
                restored.append(_restore_noneditable_keys(original[idx], item))
            else:
                restored.append(item)
        return restored
    return updated


def _payload_from_parsed_response(parsed: Any) -> dict | None:
    if not isinstance(parsed, dict):
        return None
    for key in ("resource", "payload", "updated_resource", "updated_payload"):
        value = parsed.get(key)
        if isinstance(value, dict):
            return value
    return parsed


def _refine_full_payload_with_classio(
    *,
    resource_label: str,
    payload: dict,
    prompt: str,
    context: dict | None = None,
) -> dict | None:
    import helpers.lesson_planner as lp

    editable_payload = _strip_noneditable_keys(payload or {})
    if not isinstance(editable_payload, dict) or not editable_payload:
        return None

    system_prompt = (
        "You are Classio's senior teaching-resource editor. "
        "Revise the resource to satisfy the teacher request. "
        "Return only valid JSON in this shape: {\"resource\": <complete updated resource object>}. "
        "Keep the same top-level structure and required keys unless the teacher explicitly asks for a structural change. "
        "When adding, removing, or changing questions, keep instructions, questions, and answer keys aligned. "
        "Do not include markdown, comments, explanations, or code fences."
    )
    user_prompt = json.dumps(
        {
            "resource_type": resource_label,
            "teacher_request": prompt,
            "context": context or {},
            "current_resource": editable_payload,
        },
        ensure_ascii=False,
        indent=2,
    )

    errors = []
    for provider in lp.get_ai_provider_order():
        try:
            if provider == "gemini":
                raw = lp._generate_with_gemini(system_prompt, user_prompt)
            elif provider == "openrouter":
                raw = lp._generate_with_openrouter(system_prompt, user_prompt)
            else:
                raw = lp._generate_with_openai(system_prompt, user_prompt)
            parsed = _parse_ai_json(raw)
            updated_payload = _payload_from_parsed_response(parsed)
            if isinstance(updated_payload, dict) and updated_payload:
                return _restore_noneditable_keys(payload or {}, updated_payload)
            raise ValueError("AI response did not include a usable updated resource.")
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
    logger.warning("Full resource refinement failed: %s", " | ".join(errors))
    return None


def _compact_exam_answer_payload(payload: dict) -> dict:
    exam_data = payload.get("exam_data") if isinstance(payload.get("exam_data"), dict) else {}
    answer_key = payload.get("answer_key") if isinstance(payload.get("answer_key"), dict) else {}
    sections = []
    answer_sections = answer_key.get("sections") if isinstance(answer_key.get("sections"), list) else []
    for idx, section in enumerate(exam_data.get("sections") or []):
        if not isinstance(section, dict):
            continue
        ak_section = answer_sections[idx] if idx < len(answer_sections) and isinstance(answer_sections[idx], dict) else {}
        questions = []
        for q_idx, question in enumerate(section.get("questions") or [], start=1):
            if isinstance(question, dict):
                question_payload = {
                    key: question.get(key)
                    for key in ("text", "stem", "original", "prompt", "left", "right", "word", "task", "options", "answer", "correct_answer", "correct")
                    if question.get(key) not in (None, "", [])
                }
            else:
                question_payload = {"text": str(question or "")}
            questions.append({"number": q_idx, "question": question_payload})
        sections.append(
            {
                "index": idx,
                "title": str(section.get("title") or ak_section.get("title") or ""),
                "type": str(section.get("type") or ""),
                "source_text": str(section.get("source_text") or "")[:1600],
                "questions": questions,
                "current_answers": ak_section.get("answers") if isinstance(ak_section.get("answers"), list) else [],
            }
        )
    return {"title": str(exam_data.get("title") or ""), "sections": sections}


def _exam_answer_updates_from_answer_key(answer_key: dict, fields: list[dict[str, Any]]) -> dict[str, str]:
    sections = answer_key.get("sections") if isinstance(answer_key.get("sections"), list) else []
    if not sections:
        return {}

    path_updates = _updates_from_parsed_response({"answer_key": {"sections": sections}}, fields)
    if path_updates:
        return path_updates

    updates: dict[str, str] = {}
    for idx, field in enumerate(fields):
        path = tuple(field.get("path") or ())
        if len(path) == 4 and path[0] == "answer_key" and path[1] == "sections" and path[3] == "answers" and isinstance(path[2], int):
            section_idx = path[2]
            if section_idx < len(sections) and isinstance(sections[section_idx], dict):
                answers = sections[section_idx].get("answers") or []
                if isinstance(answers, list):
                    updates[f"f{idx}"] = "\n".join(str(answer) for answer in answers if str(answer).strip())
    return updates


def _answer_key_from_parsed(parsed: Any) -> dict:
    if not isinstance(parsed, dict):
        return {}
    if isinstance(parsed.get("answer_key"), dict):
        return parsed.get("answer_key") or {}
    if isinstance(parsed.get("sections"), list):
        return {"sections": parsed.get("sections")}
    if isinstance(parsed.get("answers"), list):
        return {"sections": [{"answers": parsed.get("answers")}]} 
    return {}


def _merge_answer_key_payload(payload: dict, answer_key: dict) -> dict | None:
    sections = answer_key.get("sections") if isinstance(answer_key.get("sections"), list) else []
    if not sections:
        return None

    current_answer_key = payload.get("answer_key") if isinstance(payload.get("answer_key"), dict) else {}
    current_sections = current_answer_key.get("sections") if isinstance(current_answer_key.get("sections"), list) else []
    merged_sections = [dict(section) if isinstance(section, dict) else {} for section in current_sections]
    for idx, section in enumerate(sections):
        if not isinstance(section, dict):
            continue
        while idx >= len(merged_sections):
            merged_sections.append({})
        current_section = merged_sections[idx]
        answers = section.get("answers")
        if not isinstance(answers, list):
            continue
        merged_sections[idx] = {
            "title": str(section.get("title") or current_section.get("title") or ""),
            "answers": [answer for answer in answers if str(answer).strip()],
        }

    if not any(isinstance(section.get("answers"), list) and section.get("answers") for section in merged_sections if isinstance(section, dict)):
        return None
    updated = copy.deepcopy(payload or {})
    updated["answer_key"] = {**current_answer_key, "sections": merged_sections}
    return updated


def _refine_exam_answer_key_with_classio(*, payload: dict, prompt: str, context: dict | None = None) -> dict | None:
    import helpers.lesson_planner as lp

    compact_payload = _compact_exam_answer_payload(payload)
    if not compact_payload.get("sections"):
        return None

    system_prompt = (
        "You are Classio's exam answer-key repair editor. "
        "Use the exam questions to produce a corrected answer key only. "
        "Return only JSON in this shape: {\"answer_key\":{\"sections\":[{\"title\":\"...\",\"answers\":[\"...\"]}]}}. "
        "Keep exactly one answer-key section for each input section, in the same order. "
        "Each answers list must align item-by-item with that section's questions."
    )
    user_prompt = json.dumps(
        {
            "teacher_request": prompt,
            "context": context or {},
            "exam": compact_payload,
        },
        ensure_ascii=False,
        indent=2,
    )

    errors = []
    for provider in lp.get_ai_provider_order():
        try:
            if provider == "gemini":
                raw = lp._generate_with_gemini(system_prompt, user_prompt)
            elif provider == "openrouter":
                raw = lp._generate_with_openrouter(system_prompt, user_prompt)
            else:
                raw = lp._generate_with_openai(system_prompt, user_prompt)
            parsed = _parse_ai_json(raw)
            updated_payload = _merge_answer_key_payload(payload, _answer_key_from_parsed(parsed))
            if updated_payload:
                return updated_payload
            raise ValueError("AI response did not contain usable exam answer-key sections.")
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
    logger.warning("Exam answer-key refinement failed: %s", " | ".join(errors))
    return None


def _refine_payload_with_classio(
    *,
    resource_label: str,
    fields: list[dict[str, Any]],
    action_key_prefix: str,
    prompt: str,
    context: dict | None = None,
) -> dict[str, str]:
    import helpers.lesson_planner as lp

    system_prompt = (
        "You are Classio's senior teaching-resource editor. "
        "Revise only the editable text fields needed to satisfy the teacher request. "
        "Return only JSON in this exact shape: {\"updates\":[{\"id\":\"f0\",\"value\":\"revised text\"}]}. "
        "Use only field ids from the input. Preserve every field that does not need a change. "
        "For list fields, return one item per line in the value. Keep answer keys aligned with questions. "
        "If the teacher asks to fix answers or answer keys, update answer fields first and only change question fields when required."
    )
    user_prompt = json.dumps(
        {
            "resource_type": resource_label,
            "teacher_request": prompt,
            "context": context or {},
            "editable_fields": _field_prompt_items(fields, action_key_prefix),
        },
        ensure_ascii=False,
        indent=2,
    )

    errors = []
    for provider in lp.get_ai_provider_order():
        try:
            if provider == "gemini":
                raw = lp._generate_with_gemini(system_prompt, user_prompt)
            elif provider == "openrouter":
                raw = lp._generate_with_openrouter(system_prompt, user_prompt)
            else:
                raw = lp._generate_with_openai(system_prompt, user_prompt)
            parsed = _parse_ai_json(raw)
            cleaned = _updates_from_parsed_response(parsed, fields)
            if not cleaned:
                raise ValueError("AI response did not include usable field updates.")
            return cleaned
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
    raise RuntimeError(" | ".join(errors))


def render_resource_editor(
    *,
    resource_label: str,
    payload: dict,
    action_key_prefix: str,
    on_apply: Callable[[dict], bool],
    normalize_payload: Callable[[dict], dict] | None = None,
    context: dict | None = None,
) -> None:
    if not isinstance(payload, dict) or not payload:
        return

    with st.expander(_label("edit_resource_expander", "Edit resource"), expanded=False):
        tabs = st.tabs([t("manual_edit_tab"), t("classio_ai_refine_tab")])
        fields = _collect_editable_fields(payload)

        with tabs[0]:
            st.caption(_label("resource_json_editor_help", "Edit the resource fields, then save changes."))
            for idx, field in enumerate(fields):
                field_key = f"{action_key_prefix}_field_{idx}"
                if field_key not in st.session_state:
                    st.session_state[field_key] = str(field.get("value") or "")
                value = str(st.session_state.get(field_key) or "")
                height = 70 if len(value) < 120 and "\n" not in value else min(260, max(110, (value.count("\n") + 2) * 24))
                st.text_area(
                    _path_label(tuple(field.get("path") or ())),
                    key=field_key,
                    height=height,
                )
            if st.button(
                _label("save_resource_changes", "Save resource changes"),
                key=f"{action_key_prefix}_manual_save_resource",
                use_container_width=True,
            ):
                try:
                    updated_payload = _build_payload_from_fields(payload, fields, action_key_prefix)
                    if normalize_payload is not None:
                        updated_payload = normalize_payload(updated_payload)
                    if on_apply(updated_payload):
                        st.success(_label("resource_changes_saved", "Resource changes saved"))
                        st.rerun()
                        return
                    st.error(_label("resource_changes_save_failed", "Could not save resource changes."))
                except Exception as exc:
                    logger.exception("Manual resource edit failed")
                    st.error(_label("resource_changes_save_failed", "Could not save resource changes.") + f" {exc}")

        with tabs[1]:
            prompt_key = f"{action_key_prefix}_classio_refine_prompt"
            st.text_area(
                _label("resource_refine_prompt_label", "What should Classio fix?"),
                key=prompt_key,
                placeholder=_label(
                    "resource_refine_prompt_placeholder",
                    "Example: Fix the answer key and make Part 2 easier without changing the topic.",
                ),
                height=120,
            )
            if st.button(
                _label("refine_resource_with_classio", "Refine resource with Classio"),
                key=f"{action_key_prefix}_classio_refine_btn",
                use_container_width=True,
            ):
                refine_prompt = str(st.session_state.get(prompt_key) or "").strip()
                if not refine_prompt:
                    st.error(_label("resource_refine_prompt_required", "Tell Classio what to fix first."))
                else:
                    try:
                        updated_payload = None
                        with st.spinner(_label("resource_refine_loading", "Refining resource...")):
                            updates = {}
                            structural_refine = _wants_structural_refine(refine_prompt)
                            if structural_refine:
                                updated_payload = _refine_full_payload_with_classio(
                                    resource_label=resource_label,
                                    payload=payload,
                                    prompt=refine_prompt,
                                    context=context or {},
                                )
                            if updated_payload is None and resource_label == "exam" and _wants_answer_key_fix(refine_prompt):
                                updated_payload = _refine_exam_answer_key_with_classio(
                                    payload=payload,
                                    prompt=refine_prompt,
                                    context=context or {},
                                )
                            if updated_payload is None:
                                try:
                                    updates = _refine_payload_with_classio(
                                        resource_label=resource_label,
                                        fields=fields,
                                        action_key_prefix=action_key_prefix,
                                        prompt=refine_prompt,
                                        context=context or {},
                                    )
                                    for field_id, value in updates.items():
                                        st.session_state[f"{action_key_prefix}_field_{field_id[1:]}"] = value
                                    updated_payload = _build_payload_from_fields(payload, fields, action_key_prefix)
                                except Exception:
                                    updated_payload = _refine_full_payload_with_classio(
                                        resource_label=resource_label,
                                        payload=payload,
                                        prompt=refine_prompt,
                                        context=context or {},
                                    )
                                    if updated_payload is None:
                                        raise
                            if normalize_payload is not None:
                                updated_payload = normalize_payload(updated_payload)
                        if on_apply(updated_payload):
                            st.success(_label("resource_changes_saved", "Resource changes saved"))
                            st.rerun()
                            return
                        st.error(_label("resource_changes_save_failed", "Could not save resource changes."))
                    except Exception as exc:
                        logger.exception("Classio resource refinement failed")
                        st.error(_label("resource_refine_failed", "Classio could not refine this resource right now."))