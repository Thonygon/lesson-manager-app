from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
import html
import re

import pandas as pd
import streamlit as st

from core.database import get_sb, load_profile_row, load_table
from core.i18n import t
from core.state import get_current_user_id
from core.timezone import now_local, today_local
from helpers.calendar_helpers import build_calendar_events
from helpers.dashboard import rebuild_dashboard
from helpers.goals import get_year_goal_progress_snapshot
from helpers.practice_engine import load_in_progress_practice_session, load_practice_progress
from helpers.teacher_student_integration import (
    get_student_assignment_summary,
    load_active_linked_students_for_teacher,
    load_incoming_teacher_requests,
    load_student_assignments,
    load_student_teacher_links,
    load_teacher_assignment_progress,
)


def _uid() -> str:
    return str(get_current_user_id() or "").strip()


def _state_key(scope: str, suffix: str) -> str:
    return f"classio_notifications_{scope}_{suffix}_{_uid() or 'anon'}"


def _load_name() -> tuple[str, str]:
    uid = _uid()
    profile = load_profile_row(uid) if uid else {}
    display_name = str(
        profile.get("display_name")
        or profile.get("username")
        or st.session_state.get("user_name")
        or ""
    ).strip()
    first_name = display_name.split()[0] if display_name else ""
    return display_name, first_name or "User"


def _clean(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value) -> str:
    return _clean(value).casefold()


def _safe_title_case(value: str) -> str:
    value = _clean(value)
    return value[0].upper() + value[1:] if value else ""


def _parse_dt(value):
    try:
        dt = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(dt):
            return None
        return dt.tz_convert(None)
    except Exception:
        return None


def _format_short_date(value) -> str:
    dt = _parse_dt(value)
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d")


def _notification(
    *,
    signature: str,
    category: str,
    priority: int,
    cloud: bool,
    tone: str,
    message: str,
) -> dict:
    return {
        "signature": signature,
        "category": category,
        "priority": priority,
        "cloud": cloud,
        "tone": tone,
        "message": message,
    }


def _rows(result) -> list[dict]:
    return getattr(result, "data", None) or []


def _load_seen(scope: str) -> set[str]:
    return set(st.session_state.get(_state_key(scope, "seen"), []))


def _save_seen(scope: str, values: set[str]) -> None:
    st.session_state[_state_key(scope, "seen")] = sorted(values)


def _load_dismissed(scope: str) -> set[str]:
    return set(st.session_state.get(_state_key(scope, "dismissed"), []))


def _save_dismissed(scope: str, values: set[str]) -> None:
    st.session_state[_state_key(scope, "dismissed")] = sorted(values)


def _mark_seen(scope: str, signatures: list[str]) -> None:
    if not signatures:
        return
    seen = _load_seen(scope)
    seen.update(str(sig) for sig in signatures if str(sig).strip())
    _save_seen(scope, seen)


def _dismiss(scope: str, signature: str) -> None:
    if not signature:
        return
    dismissed = _load_dismissed(scope)
    dismissed.add(signature)
    _save_dismissed(scope, dismissed)


def _teacher_goal_milestone(progress: float) -> int:
    pct = int(progress * 100)
    for milestone in (100, 80, 60, 40, 20):
        if pct >= milestone:
            return milestone
    return 0


def _review_kind_label(value: str) -> str:
    value = _clean(value).lower()
    if value == "exam":
        return t("notification_review_kind_exam")
    if value == "worksheet":
        return t("notification_review_kind_worksheet")
    return t("notification_review_kind_work")


def _load_teacher_review_requests_for_notifications(*, teacher_id: str | None = None, student_id: str | None = None) -> list[dict]:
    teacher_id = str(teacher_id or "").strip()
    student_id = str(student_id or "").strip()
    if not teacher_id and not student_id:
        return []
    try:
        query = (
            get_sb()
            .table("teacher_review_requests")
            .select("*")
            .order("requested_at", desc=True)
        )
        if teacher_id:
            query = query.eq("teacher_id", teacher_id)
        if student_id:
            query = query.eq("student_id", student_id)
        return _rows(query.execute())
    except Exception:
        return []


def _smart_plan_state() -> dict:
    uid = _uid() or "anon"
    key = f"student_smart_plan_data_{uid}"
    state = st.session_state.get(key)
    return state if isinstance(state, dict) else {}


def _today_events_df():
    today = today_local()
    events = build_calendar_events(today, today)
    if events is None or events.empty:
        return pd.DataFrame()
    df = events.copy()
    for col in ["Student", "Time"]:
        if col not in df.columns:
            df[col] = ""
    df["Student"] = df["Student"].fillna("").astype(str).str.strip()
    df["Time"] = df["Time"].fillna("").astype(str).str.strip()
    return df


def _future_events_students(days: int = 14) -> set[str]:
    today = today_local()
    end = today + timedelta(days=days)
    events = build_calendar_events(today, end)
    if events is None or events.empty:
        return set()
    df = events.copy()
    if "Student" not in df.columns:
        return set()
    return {_norm(v) for v in df["Student"].fillna("").astype(str).tolist() if _clean(v)}


def _today_classes_logged_count() -> int:
    classes = load_table("classes")
    if classes is None or classes.empty:
        return 0
    if "lesson_date" not in classes.columns:
        return 0
    df = classes.copy()
    df["lesson_date"] = pd.to_datetime(df["lesson_date"], errors="coerce").dt.date
    return int((df["lesson_date"] == today_local()).sum())


def _payments_this_month() -> pd.DataFrame:
    payments = load_table("payments")
    if payments is None or payments.empty or "payment_date" not in payments.columns:
        return pd.DataFrame()
    df = payments.copy()
    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce")
    df = df.dropna(subset=["payment_date"])
    today = today_local()
    return df[
        (df["payment_date"].dt.year == today.year)
        & (df["payment_date"].dt.month == today.month)
    ].copy()


def _payments_this_year() -> pd.DataFrame:
    payments = load_table("payments")
    if payments is None or payments.empty or "payment_date" not in payments.columns:
        return pd.DataFrame()
    df = payments.copy()
    df["payment_date"] = pd.to_datetime(df["payment_date"], errors="coerce")
    df = df.dropna(subset=["payment_date"])
    today = today_local()
    return df[df["payment_date"].dt.year == today.year].copy()


def _classes_this_week_count() -> int:
    classes = load_table("classes")
    if classes is None or classes.empty or "lesson_date" not in classes.columns:
        return 0
    df = classes.copy()
    df["lesson_date"] = pd.to_datetime(df["lesson_date"], errors="coerce")
    df = df.dropna(subset=["lesson_date"])
    today = pd.Timestamp(today_local())
    week_start = today - pd.Timedelta(days=today.weekday())
    week_end = week_start + pd.Timedelta(days=6)
    return int(((df["lesson_date"] >= week_start) & (df["lesson_date"] <= week_end)).sum())


def get_teacher_notifications() -> list[dict]:
    uid = _uid()
    _, first_name = _load_name()
    notifications: list[dict] = []
    today = today_local()
    now = now_local()

    requests = load_incoming_teacher_requests()
    if requests:
        student_name = _safe_title_case(requests[0].get("student_name", ""))
        key = "notif_teacher_new_request_many" if len(requests) > 1 else "notif_teacher_new_request_one"
        notifications.append(_notification(
            signature="teacher_request_" + "_".join(str(r.get("id")) for r in requests[:5]),
            category="relationships",
            priority=10,
            cloud=True,
            tone="action",
            message=t(key).format(name=first_name, student=student_name, count=len(requests)),
        ))

    review_requests = []
    for row in _load_teacher_review_requests_for_notifications(teacher_id=uid):
        status = _clean(row.get("status")).lower()
        requested_at = _parse_dt(row.get("requested_at") or row.get("created_at"))
        if status == "requested" and requested_at is not None and (pd.Timestamp(now.date()) - pd.Timestamp(requested_at.date())).days <= 14:
            review_requests.append(row)
    if review_requests:
        teacher_review_student = _safe_title_case(review_requests[0].get("student_name", ""))
        if not teacher_review_student:
            try:
                student_id = str(review_requests[0].get("student_id") or "").strip()
                from helpers.teacher_student_integration import _load_profiles_map, _profile_label

                prof = _load_profiles_map([student_id]).get(student_id, {})
                teacher_review_student = _safe_title_case(_profile_label(prof))
            except Exception:
                teacher_review_student = ""
        notifications.append(_notification(
            signature="teacher_review_request_" + "_".join(str(r.get("id")) for r in review_requests[:5]),
            category="assignments",
            priority=9,
            cloud=True,
            tone="action",
            message=t(
                "notif_teacher_review_request_many" if len(review_requests) > 1 else "notif_teacher_review_request_one"
            ).format(
                name=first_name,
                student=teacher_review_student,
                count=len(review_requests),
                kind=_review_kind_label(review_requests[0].get("source_type", "")),
                title=_safe_title_case(review_requests[0].get("title", "")),
            ),
        ))

    try:
        from helpers.teacher_student_integration import get_teacher_request_resolution

        review_requests = [r for r in requests if get_teacher_request_resolution(int(r.get("id") or 0)).get("requires_choice")]
        if review_requests:
            student_name = _safe_title_case(review_requests[0].get("student_name", ""))
            key = "notif_teacher_request_review_many" if len(review_requests) > 1 else "notif_teacher_request_review_one"
            notifications.append(_notification(
                signature="teacher_request_review_" + "_".join(str(r.get("id")) for r in review_requests[:5]),
                category="relationships",
                priority=18,
                cloud=False,
                tone="info",
                message=t(key).format(name=first_name, student=student_name, count=len(review_requests)),
            ))
    except Exception:
        pass

    linked_students = load_active_linked_students_for_teacher()
    recent_links = []
    for row in linked_students:
        created_at = _parse_dt(row.get("created_at"))
        if created_at is not None and (pd.Timestamp(now.date()) - pd.Timestamp(created_at.date())).days <= 7:
            recent_links.append(row)
    if recent_links:
        student_name = _safe_title_case(recent_links[0].get("student_name", ""))
        key = "notif_teacher_linked_student_many" if len(recent_links) > 1 else "notif_teacher_linked_student_one"
        notifications.append(_notification(
            signature="teacher_linked_" + "_".join(str(r.get("id")) for r in recent_links[:5]),
            category="relationships",
            priority=35,
            cloud=True,
            tone="success",
            message=t(key).format(name=first_name, student=student_name, count=len(recent_links)),
        ))

    today_events = _today_events_df()
    if not today_events.empty:
        notifications.append(_notification(
            signature=f"teacher_today_lessons_{today.isoformat()}_{len(today_events)}",
            category="schedule",
            priority=40,
            cloud=True,
            tone="info",
            message=t("notif_teacher_upcoming_lessons_today").format(name=first_name, count=len(today_events)),
        ))

        last_time = sorted([_clean(v) for v in today_events["Time"].tolist() if _clean(v)])[-1]
        m = re.match(r"^(\d{1,2}):(\d{2})", last_time)
        after_last = now.hour >= 18
        if m:
            hh, mm = int(m.group(1)), int(m.group(2))
            after_last = (now.hour, now.minute) >= (hh, mm)
        logged = _today_classes_logged_count()
        if after_last and logged < len(today_events):
            notifications.append(_notification(
                signature=f"teacher_record_lessons_{today.isoformat()}_{len(today_events)}_{logged}",
                category="schedule",
                priority=15,
                cloud=True,
                tone="action",
                message=t("notif_teacher_record_lessons").format(name=first_name, count=len(today_events)),
            ))

    month_payments = _payments_this_month()
    if linked_students and month_payments.empty:
        notifications.append(_notification(
            signature=f"teacher_no_payments_{today.year}_{today.month}",
            category="money",
            priority=20,
            cloud=True,
            tone="warning",
            message=t("notif_teacher_no_payments_month").format(name=first_name),
        ))
    elif not month_payments.empty and len(month_payments) == 1:
        notifications.append(_notification(
            signature=f"teacher_first_payment_{today.year}_{today.month}",
            category="money",
            priority=85,
            cloud=False,
            tone="success",
            message=t("notif_teacher_first_payment_month").format(name=first_name),
        ))

    dash = rebuild_dashboard(active_window_days=183, expiry_days=365, grace_days=35)
    if dash is not None and not dash.empty:
        d = dash.copy()
        d["Status"] = d.get("Status", "").fillna("").astype(str).str.strip().str.casefold()
        due_df = d[d["Status"] == "almost_finished"].copy()
        if not due_df.empty:
            due_names = [_safe_title_case(v) for v in due_df.get("Student", []).tolist() if _clean(v)]
            key = "notif_teacher_package_ending_many" if len(due_df) > 1 else "notif_teacher_package_ending_one"
            notifications.append(_notification(
                signature=f"teacher_package_ending_{today.isoformat()}_{len(due_df)}",
                category="money",
                priority=12,
                cloud=True,
                tone="action",
                message=t(key).format(name=first_name, student=(due_names[0] if due_names else ""), count=len(due_df)),
            ))
            if len(due_df) >= 2:
                notifications.append(_notification(
                    signature=f"teacher_renewal_followup_{today.isoformat()}_{len(due_df)}",
                    category="money",
                    priority=42,
                    cloud=True,
                    tone="info",
                    message=t("notif_teacher_renewal_followup").format(name=first_name, count=len(due_df)),
                ))

        inactive_df = d[d["Status"] == "finished"].copy()
        if not inactive_df.empty:
            notifications.append(_notification(
                signature=f"teacher_inactive_students_{today.isoformat()}_{len(inactive_df)}",
                category="growth",
                priority=80,
                cloud=False,
                tone="info",
                message=t("notif_teacher_inactive_students").format(name=first_name, count=len(inactive_df)),
            ))

    assignment_progress = load_teacher_assignment_progress()
    completed = []
    overdue = []
    not_started = []
    started = []
    topic_completed = []
    for row in assignment_progress:
        status = _clean(row.get("status")).lower()
        updated_at = _parse_dt(row.get("updated_at") or row.get("completed_at") or row.get("graded_at"))
        age_days = None
        if updated_at is not None:
            age_days = (pd.Timestamp(now.date()) - pd.Timestamp(updated_at.date())).days

        if status in {"graded", "completed"} and (age_days is None or age_days <= 7):
            completed.append(row)
            if row.get("assignment_type") == "lesson_plan_topic":
                topic_completed.append(row)
        elif status == "overdue":
            overdue.append(row)
        elif status == "assigned":
            created_at = _parse_dt(row.get("created_at"))
            if created_at is not None and (pd.Timestamp(now.date()) - pd.Timestamp(created_at.date())).days >= 2:
                not_started.append(row)
        elif status == "started":
            started.append(row)

    if completed:
        key = "notif_teacher_assignment_completed_many" if len(completed) > 1 else "notif_teacher_assignment_completed_one"
        notifications.append(_notification(
            signature="teacher_assignment_completed_" + "_".join(str(r.get("id")) for r in completed[:5]),
            category="assignments",
            priority=16,
            cloud=True,
            tone="success",
            message=t(key).format(name=first_name, student=_safe_title_case(completed[0].get("student_name", "")), count=len(completed)),
        ))
    if overdue:
        key = "notif_teacher_assignment_overdue_many" if len(overdue) > 1 else "notif_teacher_assignment_overdue_one"
        notifications.append(_notification(
            signature="teacher_assignment_overdue_" + "_".join(str(r.get("id")) for r in overdue[:5]),
            category="assignments",
            priority=14,
            cloud=True,
            tone="warning",
            message=t(key).format(name=first_name, student=_safe_title_case(overdue[0].get("student_name", "")), count=len(overdue)),
        ))
    if not_started:
        key = "notif_teacher_assignment_not_started_many" if len(not_started) > 1 else "notif_teacher_assignment_not_started_one"
        notifications.append(_notification(
            signature="teacher_assignment_not_started_" + "_".join(str(r.get("id")) for r in not_started[:5]),
            category="assignments",
            priority=24,
            cloud=True,
            tone="warning",
            message=t(key).format(name=first_name, student=_safe_title_case(not_started[0].get("student_name", "")), count=len(not_started)),
        ))
    if started:
        key = "notif_teacher_assignment_started_many" if len(started) > 1 else "notif_teacher_assignment_started_one"
        notifications.append(_notification(
            signature="teacher_assignment_started_" + "_".join(str(r.get("id")) for r in started[:5]),
            category="assignments",
            priority=75,
            cloud=False,
            tone="info",
            message=t(key).format(name=first_name, student=_safe_title_case(started[0].get("student_name", "")), count=len(started)),
        ))
    if topic_completed:
        key = "notif_teacher_topic_completed_many" if len(topic_completed) > 1 else "notif_teacher_topic_completed_one"
        notifications.append(_notification(
            signature="teacher_topic_completed_" + "_".join(str(r.get("id")) for r in topic_completed[:5]),
            category="assignments",
            priority=78,
            cloud=False,
            tone="success",
            message=t(key).format(name=first_name, student=_safe_title_case(topic_completed[0].get("student_name", "")), count=len(topic_completed)),
        ))

    future_students = _future_events_students(days=14)
    unscheduled = [row for row in linked_students if _norm(row.get("student_name")) not in future_students]
    if unscheduled:
        key = "notif_teacher_no_upcoming_lesson_many" if len(unscheduled) > 1 else "notif_teacher_no_upcoming_lesson_one"
        notifications.append(_notification(
            signature="teacher_no_upcoming_" + "_".join(str(r.get("id")) for r in unscheduled[:5]),
            category="schedule",
            priority=38,
            cloud=True,
            tone="info",
            message=t(key).format(name=first_name, student=_safe_title_case(unscheduled[0].get("student_name", "")), count=len(unscheduled)),
        ))

    goal_snapshot = get_year_goal_progress_snapshot()
    milestone = _teacher_goal_milestone(float(goal_snapshot.get("progress") or 0.0))
    if milestone >= 20:
        key = "notif_teacher_goal_reached" if milestone >= 100 else "notif_teacher_goal_milestone"
        notifications.append(_notification(
            signature=f"teacher_goal_{goal_snapshot.get('year')}_{milestone}",
            category="growth",
            priority=22,
            cloud=True,
            tone="success",
            message=t(key).format(name=first_name, percent=milestone),
        ))

    week_lessons = _classes_this_week_count()
    if week_lessons >= 5:
        notifications.append(_notification(
            signature=f"teacher_lessons_week_{today.isocalendar().week}_{week_lessons}",
            category="growth",
            priority=88,
            cloud=False,
            tone="success",
            message=t("notif_teacher_lessons_this_week").format(name=first_name, count=week_lessons),
        ))

    if len(linked_students) < 3:
        notifications.append(_notification(
            signature=f"teacher_growth_prompt_{len(linked_students)}_{today.isoformat()}",
            category="growth",
            priority=95,
            cloud=False,
            tone="info",
            message=t("notif_teacher_growth_prompt").format(name=first_name),
        ))

    return sorted(notifications, key=lambda item: (item["priority"], item["message"]))


def get_student_notifications() -> list[dict]:
    uid = _uid()
    _, first_name = _load_name()
    notifications: list[dict] = []
    today = today_local()
    now = now_local()

    assignments = load_student_assignments(statuses=["assigned", "started", "submitted", "graded", "completed", "overdue"])
    assigned = []
    due_soon = []
    overdue = []
    graded = []
    topics = []
    exam_continue = []
    for row in assignments:
        status = _clean(row.get("status")).lower()
        created_at = _parse_dt(row.get("created_at"))
        due_at = _parse_dt(row.get("due_at"))
        assignment_type = _clean(row.get("assignment_type")).lower()
        if status == "assigned" and created_at is not None and (pd.Timestamp(now.date()) - pd.Timestamp(created_at.date())).days <= 7:
            assigned.append(row)
            if assignment_type == "lesson_plan_topic":
                topics.append(row)
        if due_at is not None and status in {"assigned", "started"}:
            delta_days = (pd.Timestamp(due_at.date()) - pd.Timestamp(today)).days
            if 0 <= delta_days <= 2:
                due_soon.append(row)
        if status == "overdue":
            overdue.append(row)
        if status == "graded":
            graded.append(row)
        if assignment_type == "exam" and (status == "started" or load_in_progress_practice_session("exam", row.get("id"))):
            exam_continue.append(row)

    if assigned:
        regular_assigned = [r for r in assigned if _clean(r.get("assignment_type")).lower() != "lesson_plan_topic"]
        if regular_assigned:
            key = "notif_student_new_assignment_many" if len(regular_assigned) > 1 else "notif_student_new_assignment_one"
            notifications.append(_notification(
                signature="student_new_assignment_" + "_".join(str(r.get("id")) for r in regular_assigned[:5]),
                category="assignments",
                priority=10,
                cloud=True,
                tone="action",
                message=t(key).format(name=first_name, teacher=_safe_title_case(regular_assigned[0].get("teacher_name", "")), count=len(regular_assigned)),
            ))
    if due_soon:
        key = "notif_student_due_soon_many" if len(due_soon) > 1 else "notif_student_due_soon_one"
        notifications.append(_notification(
            signature="student_due_soon_" + "_".join(str(r.get("id")) for r in due_soon[:5]),
            category="assignments",
            priority=12,
            cloud=True,
            tone="warning",
            message=t(key).format(name=first_name, title=_safe_title_case(due_soon[0].get("title", "")), count=len(due_soon)),
        ))
    if overdue:
        key = "notif_student_overdue_many" if len(overdue) > 1 else "notif_student_overdue_one"
        notifications.append(_notification(
            signature="student_overdue_" + "_".join(str(r.get("id")) for r in overdue[:5]),
            category="assignments",
            priority=8,
            cloud=True,
            tone="warning",
            message=t(key).format(name=first_name, title=_safe_title_case(overdue[0].get("title", "")), count=len(overdue)),
        ))
    if graded:
        key = "notif_student_graded_many" if len(graded) > 1 else "notif_student_graded_one"
        notifications.append(_notification(
            signature="student_graded_" + "_".join(str(r.get("id")) for r in graded[:5]),
            category="assignments",
            priority=20,
            cloud=True,
            tone="success",
            message=t(key).format(name=first_name, title=_safe_title_case(graded[0].get("title", "")), count=len(graded)),
        ))
    if exam_continue:
        notifications.append(_notification(
            signature="student_exam_continue_" + "_".join(str(r.get("id")) for r in exam_continue[:5]),
            category="assignments",
            priority=16,
            cloud=True,
            tone="info",
            message=t("notif_student_saved_exam").format(name=first_name),
        ))
    if topics:
        key = "notif_student_new_topic_many" if len(topics) > 1 else "notif_student_new_topic_one"
        notifications.append(_notification(
            signature="student_topics_" + "_".join(str(r.get("id")) for r in topics[:5]),
            category="relationships",
            priority=42,
            cloud=False,
            tone="info",
            message=t(key).format(name=first_name, title=_safe_title_case(topics[0].get("title", "")), count=len(topics)),
        ))

    relationships = load_student_teacher_links()
    accepted = []
    for row in relationships:
        if _clean(row.get("status")).lower() == "active":
            responded_at = _parse_dt(row.get("responded_at") or row.get("updated_at"))
            if responded_at is not None and (pd.Timestamp(now.date()) - pd.Timestamp(responded_at.date())).days <= 7:
                accepted.append(row)
    if accepted:
        key = "notif_student_teacher_accepted_many" if len(accepted) > 1 else "notif_student_teacher_accepted_one"
        notifications.append(_notification(
            signature="student_teacher_accepted_" + "_".join(str(r.get("id")) for r in accepted[:5]),
            category="relationships",
            priority=44,
            cloud=False,
            tone="success",
            message=t(key).format(name=first_name, teacher=_safe_title_case(accepted[0].get("teacher_name", "")), count=len(accepted)),
        ))

    reviewed_requests = []
    for row in _load_teacher_review_requests_for_notifications(student_id=uid):
        status = _clean(row.get("status")).lower()
        reviewed_at = _parse_dt(row.get("reviewed_at"))
        if status == "reviewed" and reviewed_at is not None and (pd.Timestamp(now.date()) - pd.Timestamp(reviewed_at.date())).days <= 14:
            reviewed_requests.append(row)
    if reviewed_requests:
        teacher_name = ""
        try:
            teacher_id = str(reviewed_requests[0].get("teacher_id") or "").strip()
            from helpers.teacher_student_integration import _load_profiles_map, _profile_label

            prof = _load_profiles_map([teacher_id]).get(teacher_id, {})
            teacher_name = _safe_title_case(_profile_label(prof))
        except Exception:
            teacher_name = ""
        notifications.append(_notification(
            signature="student_review_completed_" + "_".join(str(r.get("id")) for r in reviewed_requests[:5]),
            category="assignments",
            priority=11,
            cloud=True,
            tone="success",
            message=t(
                "notif_student_review_completed_many" if len(reviewed_requests) > 1 else "notif_student_review_completed_one"
            ).format(
                name=first_name,
                teacher=teacher_name,
                count=len(reviewed_requests),
                kind=_review_kind_label(reviewed_requests[0].get("source_type", "")),
                title=_safe_title_case(reviewed_requests[0].get("title", "")),
            ),
        ))

    smart_plan = _smart_plan_state()
    if smart_plan.get("setup_complete"):
        tasks = smart_plan.get("tasks") or []
        completed_today = [item for item in tasks if item.get("done")]
        if smart_plan.get("generated_for") == today.isoformat() and tasks and len(completed_today) < len(tasks):
            notifications.append(_notification(
                signature=f"student_smart_plan_ready_{today.isoformat()}_{len(tasks)}",
                category="smart_plan",
                priority=50,
                cloud=False,
                tone="info",
                message=t("notif_student_smart_plan_ready").format(name=first_name),
            ))

        if tasks and len(completed_today) < len(tasks) and smart_plan.get("last_completion_date") != today.isoformat() and now.hour >= 16:
            notifications.append(_notification(
                signature=f"student_streak_risk_{today.isoformat()}_{len(completed_today)}_{len(tasks)}",
                category="smart_plan",
                priority=14,
                cloud=True,
                tone="warning",
                message=t("notif_student_streak_risk").format(name=first_name),
            ))

        if tasks and len(completed_today) == len(tasks):
            notifications.append(_notification(
                signature=f"student_weekly_milestone_{today.isoformat()}_{smart_plan.get('streak', 0)}",
                category="progress",
                priority=70,
                cloud=False,
                tone="success",
                message=t("notif_student_weekly_milestone").format(name=first_name),
            ))

    progress = load_practice_progress()
    if progress is not None and not progress.empty:
        total_xp = int(pd.to_numeric(progress.get("total_xp"), errors="coerce").fillna(0).sum()) if "total_xp" in progress.columns else 0
        attempted = int(pd.to_numeric(progress.get("total_attempted"), errors="coerce").fillna(0).sum()) if "total_attempted" in progress.columns else 0
        correct = int(pd.to_numeric(progress.get("total_correct"), errors="coerce").fillna(0).sum()) if "total_correct" in progress.columns else 0
        accuracy = int(round((correct / attempted) * 100)) if attempted else 0
        if total_xp >= 100 or accuracy >= 80:
            notifications.append(_notification(
                signature=f"student_progress_{total_xp}_{accuracy}",
                category="progress",
                priority=82,
                cloud=False,
                tone="success",
                message=t("notif_student_progress_milestone").format(name=first_name),
            ))

    return sorted(notifications, key=lambda item: (item["priority"], item["message"]))


def _inject_notification_styles() -> None:
    st.markdown(
        """
        <style>
        .classio-notification-cloud {
            position: relative;
            overflow: hidden;
            border-radius: 22px;
            padding: 18px 20px 16px;
            background:
              radial-gradient(circle at top right, rgba(59,130,246,.08), transparent 34%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 84%, white 16%));
            border: 1px solid color-mix(in srgb, var(--border) 74%, rgba(59,130,246,.20) 26%);
            box-shadow: 0 14px 34px rgba(15,23,42,.08);
            margin: 0.5rem 0 1rem;
        }
        .classio-notification-cloud::after {
            content: "";
            position: absolute;
            left: 34px;
            bottom: -10px;
            width: 18px;
            height: 18px;
            background: var(--panel);
            border-left: 1px solid color-mix(in srgb, var(--border) 74%, rgba(59,130,246,.20) 26%);
            border-bottom: 1px solid color-mix(in srgb, var(--border) 74%, rgba(59,130,246,.20) 26%);
            transform: rotate(-45deg);
        }
        .classio-notification-kicker {
            font-size: 0.78rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: .06em;
            color: var(--muted);
            margin-bottom: 0.45rem;
        }
        .classio-notification-message {
            font-size: 1rem;
            line-height: 1.55;
            color: var(--text);
            font-weight: 700;
        }
        .classio-notification-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 1.7rem;
            height: 1.7rem;
            padding: 0 0.5rem;
            border-radius: 999px;
            background: linear-gradient(135deg, rgba(59,130,246,.16), rgba(99,102,241,.18));
            border: 1px solid rgba(59,130,246,.22);
            color: var(--text);
            font-size: 0.8rem;
            font-weight: 800;
            margin-top: 0.15rem;
        }
        .classio-notification-panel-head {
            display: flex;
            align-items: center;
            gap: 0.6rem;
            margin: 1.35rem 0 0.85rem;
            flex-wrap: nowrap;
        }
        .classio-notification-panel-heading {
            display: inline-flex;
            align-items: center;
            gap: 0.55rem;
            margin: 1.35rem 0 0.85rem;
            width: fit-content;
        }
        .classio-notification-panel-heading-text {
            font-size: clamp(1.75rem, 2.2vw, 2.15rem);
            font-weight: 700;
            line-height: 1.2;
            letter-spacing: -0.03em;
            color: var(--text);
            margin: 0;
        }
        .classio-notification-panel {
            margin-top: 0.85rem;
            padding: 0.25rem 0 0.2rem;
        }
        .classio-notification-group {
            margin: 0.85rem 0 1rem;
        }
        .classio-notification-group-title {
            font-size: 0.82rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: var(--muted);
            margin-bottom: 0.55rem;
        }
        .classio-notification-item {
            position: relative;
            overflow: hidden;
            border-radius: 18px;
            padding: 14px 16px;
            margin-bottom: 0.65rem;
            background:
              radial-gradient(circle at top right, rgba(59,130,246,.05), transparent 34%),
              linear-gradient(180deg, var(--panel), color-mix(in srgb, var(--panel) 88%, white 12%));
            border: 1px solid color-mix(in srgb, var(--border) 80%, rgba(59,130,246,.14) 20%);
            box-shadow: 0 10px 24px rgba(15,23,42,.06);
        }
        .classio-notification-item::before {
            content: "";
            position: absolute;
            inset: 0 auto 0 0;
            width: 4px;
            background: linear-gradient(180deg, #38bdf8, #6366f1 55%, #14b8a6);
        }
        .classio-notification-item-message {
            color: var(--text);
            font-weight: 700;
            line-height: 1.5;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _group_label(category: str) -> str:
    mapping = {
        "assignments": t("notification_group_assignments"),
        "money": t("notification_group_money"),
        "schedule": t("notification_group_schedule"),
        "growth": t("notification_group_growth"),
        "relationships": t("notification_group_relationships"),
        "smart_plan": t("notification_group_smart_plan"),
        "progress": t("notification_group_progress"),
    }
    return mapping.get(category, t("notification_group_updates"))


def _speaker_title(scope: str) -> str:
    return t("notification_teacher_assistant") if scope == "teacher" else t("notification_student_assistant")


def render_notification_cloud(notifications: list[dict], *, scope: str) -> None:
    _inject_notification_styles()
    dismissed = _load_dismissed(scope)
    candidates = [n for n in notifications if n.get("cloud") and n.get("signature") not in dismissed]
    if not candidates:
        return
    top = sorted(candidates, key=lambda item: (item["priority"], item["message"]))[0]
    _mark_seen(scope, [top["signature"]])
    cloud_col, close_col = st.columns([20, 1], gap="small")
    with cloud_col:
        st.markdown(
            f"""
            <div class="classio-notification-cloud">
                <div class="classio-notification-kicker">{html.escape(_speaker_title(scope))}</div>
                <div class="classio-notification-message">{html.escape(top['message'])}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with close_col:
        if st.button("✕", key=f"{scope}_notif_cloud_close_{top['signature']}", help=t("close")):
            _dismiss(scope, top["signature"])
            st.rerun()

def render_notification_panel(
    notifications: list[dict],
    *,
    scope: str,
    toggle_key: str,
) -> None:
    _inject_notification_styles()
    if not notifications:
        return

    seen = _load_seen(scope)
    unseen = [n for n in notifications if n.get("signature") not in seen]
    unseen_count = len(unseen)

    toggle_col, spacer_col = st.columns([3, 9], gap="small")
    with toggle_col:
        show_all = st.toggle(
            t("notification_show_all"),
            value=False,
            key=toggle_key,
        )
    if show_all and unseen_count > 0:
        _mark_seen(scope, [n["signature"] for n in unseen])
        unseen_count = 0
    with spacer_col:
        st.markdown("", unsafe_allow_html=True)

    if not show_all:
        return
    grouped: dict[str, list[dict]] = defaultdict(list)
    for item in notifications:
        grouped[item.get("category") or "updates"].append(item)

    st.markdown("<div class='classio-notification-panel'>", unsafe_allow_html=True)
    category_order = ["assignments", "money", "schedule", "relationships", "smart_plan", "progress", "growth"]
    for category in category_order:
        rows = grouped.get(category) or []
        if not rows:
            continue
        st.markdown(f"<div class='classio-notification-group-title'>{html.escape(_group_label(category))}</div>", unsafe_allow_html=True)
        for row in rows:
            st.markdown(
                f"<div class='classio-notification-item'><div class='classio-notification-item-message'>{html.escape(row['message'])}</div></div>",
                unsafe_allow_html=True,
            )
    st.markdown("</div>", unsafe_allow_html=True)


def render_notification_heading(
    notifications: list[dict],
    *,
    scope: str,
    title_text: str | None = None,
) -> None:
    _inject_notification_styles()
    if title_text is None:
        title_text = t("notifications")
    seen = _load_seen(scope)
    unseen_count = len([n for n in notifications if n.get("signature") not in seen])
    st.markdown(
        (
            "<div class='classio-notification-panel-heading'>"
            f"<div class='classio-notification-panel-heading-text'>{html.escape(title_text)}</div>"
            + (
                f"<div class='classio-notification-badge'>{unseen_count}</div>"
                if unseen_count > 0
                else ""
            )
            + "</div>"
        ),
        unsafe_allow_html=True,
    )
