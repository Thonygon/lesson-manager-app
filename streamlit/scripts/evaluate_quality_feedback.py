"""Read-only beta feedback report. No model is trained or promoted here."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TABLE_COLUMNS = {
    "classio_generation_intent_feedback": "generation_id,feature_name,feedback_surface,satisfied,reason,answered_at",
    "classio_explorer_generation_feedback": "operation_id,feature_name,feedback_surface,satisfied,reason,answered_at",
    "classio_teacher_relevance_feedback": "exposure_id,reason,active,resource_is_public,topic_id,updated_at",
    "classio_teacher_relevance_feedback_events": "action,created_at",
    "resource_exposures": "exposure_id,exposure_type,shown_at",
    "resource_exposure_events": "exposure_id,event_type,event_at",
}


def _since(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("--since needs a timezone")
    return parsed.astimezone(timezone.utc)


def _after(value: object, since: datetime) -> bool:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(timezone.utc) >= since
    except (ValueError, TypeError):
        return False


def build_report(snapshot: dict, since: datetime) -> dict:
    generations = [row for row in snapshot.get("classio_generation_intent_feedback", []) if _after(row.get("answered_at"), since)]
    explorer = [row for row in snapshot.get("classio_explorer_generation_feedback", []) if _after(row.get("answered_at"), since)]
    rejected = [row for row in snapshot.get("classio_teacher_relevance_feedback", []) if row.get("active") is True and _after(row.get("updated_at"), since)]
    events = [row for row in snapshot.get("classio_teacher_relevance_feedback_events", []) if _after(row.get("created_at"), since)]
    displayed = {str(row.get("exposure_id")) for row in snapshot.get("resource_exposures", []) if row.get("exposure_type") == "teacher_resource_recommendation" and _after(row.get("shown_at"), since)}
    assigned = {str(row.get("exposure_id")) for row in snapshot.get("resource_exposure_events", []) if row.get("event_type") == "assigned" and _after(row.get("event_at"), since)} & displayed
    topical_negatives = {str(row.get("exposure_id")) for row in rejected if row.get("reason") == "wrong_topic" and row.get("resource_is_public") is True and row.get("topic_id")} & displayed
    contradictions = assigned & topical_negatives
    generation_by_surface = Counter(str(row.get("feedback_surface") or "unknown") for row in generations)
    generation_by_feature = Counter(str(row.get("feature_name") or "unknown") for row in generations)
    generation_yes = sum(row.get("satisfied") is True for row in generations)
    generation_no = sum(row.get("satisfied") is False for row in generations)
    return {
        "since": since.isoformat(),
        "generation_intent": {
            "answers": len(generations), "yes": generation_yes, "no": generation_no,
            "by_surface": dict(generation_by_surface), "by_feature": dict(generation_by_feature),
            "negative_reasons": dict(Counter(str(row.get("reason")) for row in generations if row.get("satisfied") is False and row.get("reason"))),
        },
        "explorer_intent": {
            "answers": len(explorer),
            "yes": sum(row.get("satisfied") is True for row in explorer),
            "no": sum(row.get("satisfied") is False for row in explorer),
            "by_feature": dict(Counter(str(row.get("feature_name") or "unknown") for row in explorer)),
            "negative_reasons": dict(Counter(str(row.get("reason")) for row in explorer if row.get("satisfied") is False and row.get("reason"))),
        },
        "teacher_relevance": {
            "active_wrong_topic": sum(row.get("reason") == "wrong_topic" for row in rejected),
            "active_student_unfit": sum(row.get("reason") == "student_unfit" for row in rejected),
            "undo_events": sum(row.get("action") == "undone" for row in events),
            "public_topic_labels_eligible_for_review": len(topical_negatives),
        },
        "observed_confusion": {
            "description": "Displayed recommendations only; assignment is a weak positive and wrong_topic is an explicit negative. Unshown candidates have no observed label.",
            "true_positive": len(assigned - contradictions),
            "false_positive": len(topical_negatives - contradictions),
            "false_negative": None, "true_negative": None,
            "contradictory_exposures_excluded": len(contradictions),
        },
    }


def _fetch_table(base: str, key: str, table: str, columns: str, since: datetime) -> list[dict]:
    date_column = {"classio_generation_intent_feedback": "answered_at", "classio_explorer_generation_feedback": "answered_at", "classio_teacher_relevance_feedback": "updated_at", "classio_teacher_relevance_feedback_events": "created_at", "resource_exposures": "shown_at", "resource_exposure_events": "event_at"}[table]
    result: list[dict] = []
    for offset in range(0, 100000, 1000):
        query = urlencode({"select": columns, date_column: f"gte.{since.isoformat()}", "limit": "1000", "offset": str(offset), "order": f"{date_column}.asc"})
        request = Request(f"{base.rstrip('/')}/rest/v1/{table}?{query}", headers={"apikey": key, "Authorization": f"Bearer {key}", "Accept": "application/json"})
        with urlopen(request, timeout=20) as response:
            page = json.load(response)
        if not isinstance(page, list):
            raise RuntimeError(f"Unexpected {table} response")
        result.extend(page)
        if len(page) < 1000:
            return result
    raise RuntimeError(f"{table} exceeds the report page limit")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", required=True, help="Beta release timestamp in ISO 8601 with timezone")
    parser.add_argument("--snapshot", type=Path, help="Use a local exported JSON snapshot instead of Supabase")
    parser.add_argument("--output", type=Path, help="Write the metadata-only JSON report")
    args = parser.parse_args()
    since = _since(args.since)
    if args.snapshot:
        snapshot = json.loads(args.snapshot.read_text())
    else:
        base = os.getenv("SUPABASE_URL", "")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not base or not key:
            parser.error("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required without --snapshot")
        snapshot = {table: _fetch_table(base, key, table, columns, since) for table, columns in TABLE_COLUMNS.items()}
    report = build_report(snapshot, since)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
