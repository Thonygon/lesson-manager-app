import unittest
import importlib
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

from app_pages.student_assignments import (
    _assignment_scope_groups,
    _program_subject_groups,
)
from app_pages.student_practice import _practice_subject_groups
from helpers.learning_programs import (
    _canonicalize_program_identifiers,
    _resolve_existing_program_unit_id,
    _scoped_expander_label,
    _sanitize_loaded_program_identifiers,
    load_learning_program,
)
from helpers.resource_gallery import resource_kind_accent


class StudentPageScopingTests(unittest.TestCase):
    def test_canonical_program_ids_are_rewritten_by_position(self):
        corrupted = {
            "units": [
                {
                    "unit_number": 1,
                    "unit_id": 696,
                    "title": "Foundations",
                    "topics": [{"topic_id": 2762, "unit_id": 696, "title": "Introductions"}],
                },
                {
                    "unit_number": 7,
                    "unit_id": 696,
                    "title": "Travel and Adventure",
                    "topics": [{"topic_id": 2762, "unit_id": 696, "title": "Travel plans"}],
                },
            ]
        }

        canonical = _canonicalize_program_identifiers(
            corrupted,
            unit_ids_by_number={1: 701, 7: 696},
            topic_ids_by_position={(1, 1): 3001, (7, 1): 3007},
        )

        self.assertEqual([701, 696], [unit["unit_id"] for unit in canonical["units"]])
        self.assertEqual([3001, 3007], [
            unit["topics"][0]["topic_id"] for unit in canonical["units"]
        ])
        self.assertEqual([701, 696], [
            unit["topics"][0]["unit_id"] for unit in canonical["units"]
        ])

    def test_loader_rejects_topic_foreign_key_with_a_different_unit_position(self):
        program_data = {
            "title": "English B1",
            "units": [
                {
                    "unit_number": 1,
                    "unit_id": 696,
                    "title": "Foundations",
                    "topics": [{
                        "topic_id": 2762,
                        "unit_id": 696,
                        "title": "Introductions",
                        "learning_objectives": ["Introduce yourself"],
                    }],
                },
                {
                    "unit_number": 7,
                    "unit_id": 696,
                    "title": "Travel and Adventure",
                    "topics": [{
                        "topic_id": 2762,
                        "unit_id": 696,
                        "title": "Travel plans",
                        "learning_objectives": ["Discuss travel plans"],
                    }],
                },
            ],
        }
        rows_by_table = {
            "learning_programs": [{
                "id": 7,
                "subject": "english",
                "program_data": program_data,
            }],
            # The legacy corruption moved row 696 from Unit 1 to Unit 7.
            "learning_program_units": [{
                "id": 696,
                "program_id": 7,
                "unit_number": 7,
                "title": "Travel and Adventure",
            }],
            # Its old topics still correctly say they belong to Unit 1.
            "learning_program_topics": [{
                "id": 2762,
                "program_id": 7,
                "unit_id": 696,
                "unit_number": 1,
                "topic_number": 1,
                "title": "Introductions",
                "learning_objectives": ["Introduce yourself"],
            }],
        }

        class Query:
            def __init__(self, rows):
                self.rows = rows

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, *_args, **_kwargs):
                return self

            def limit(self, *_args, **_kwargs):
                return self

            def order(self, *_args, **_kwargs):
                return self

            def execute(self):
                return SimpleNamespace(data=self.rows)

        class Supabase:
            def table(self, name):
                return Query(rows_by_table[name])

        load_learning_program.clear()
        try:
            with patch("helpers.learning_programs.get_sb", return_value=Supabase()):
                loaded = load_learning_program(7)
        finally:
            load_learning_program.clear()

        self.assertEqual(["Foundations", "Travel and Adventure"], [
            unit["title"] for unit in loaded["units"]
        ])
        self.assertEqual(2762, loaded["units"][0]["topics"][0]["topic_id"])
        self.assertEqual(0, loaded["units"][1]["topics"][0]["topic_id"])
        self.assertEqual("Travel plans", loaded["units"][1]["topics"][0]["title"])

    def test_legacy_duplicate_program_ids_are_visible_without_mixed_progress(self):
        corrupted = {
            "units": [
                {
                    "unit_number": 1,
                    "unit_id": 696,
                    "title": "English Foundations",
                    "topics": [
                        {"topic_id": 2762, "title": "Introductions"},
                        {"topic_id": 2763, "title": "Daily life"},
                    ],
                },
                {
                    "unit_number": 7,
                    "unit_id": 696,
                    "title": "Travel and Adventure",
                    "topics": [
                        {"topic_id": 2762, "title": "Travel plans"},
                        {"topic_id": 2763, "title": "At the airport"},
                    ],
                },
            ]
        }

        loaded = _sanitize_loaded_program_identifiers(corrupted)

        self.assertEqual(2, len(loaded["units"]))
        self.assertEqual(["Travel plans", "At the airport"], [
            topic["title"] for topic in loaded["units"][1]["topics"]
        ])
        self.assertEqual([2762, 2763], [
            topic["topic_id"] for topic in loaded["units"][0]["topics"]
        ])
        self.assertEqual([0, 0], [
            topic["topic_id"] for topic in loaded["units"][1]["topics"]
        ])
        self.assertEqual(
            len({
                topic["topic_id"]
                for unit in loaded["units"]
                for topic in unit["topics"]
                if topic["topic_id"] > 0
            }),
            sum(
                topic["topic_id"] > 0
                for unit in loaded["units"]
                for topic in unit["topics"]
            ),
        )

    def test_program_update_does_not_move_a_unit_row_to_another_position(self):
        existing_units = {1: 696}
        unit_rows_by_id = {696: {"id": 696, "unit_number": 1}}

        unit_one_id = _resolve_existing_program_unit_id(
            target_unit_number=1,
            requested_unit_id=696,
            unit_lookup_by_number=existing_units,
            unit_rows_by_id=unit_rows_by_id,
            claimed_unit_ids=set(),
        )
        unit_seven_id = _resolve_existing_program_unit_id(
            target_unit_number=7,
            requested_unit_id=696,
            unit_lookup_by_number=existing_units,
            unit_rows_by_id=unit_rows_by_id,
            claimed_unit_ids={unit_one_id},
        )

        self.assertEqual(696, unit_one_id)
        self.assertEqual(0, unit_seven_id)

    def test_teacher_program_with_legacy_duplicate_topic_ids_renders(self):
        app = AppTest.from_string(
            """
from app_pages import app_page_students as students_page

students_page.load_assignment_progress_map = lambda _assignment_id: {}
students_page.inject_resource_gallery_styles = lambda: None
students_page.extract_gallery_image_url = lambda _program: ""
students_page.render_gallery_card_html = lambda **kwargs: kwargs.get("title", "")
students_page._render_teacher_program_pagination = lambda *_args, **_kwargs: None

row = {
    "id": 201,
    "student_name": "Student",
    "subject_display": "English",
    "program": {
        "title": "English Program",
        "units": [
            {
                "unit_number": 1,
                "title": "Foundations",
                "topics": [{"topic_id": 2762, "title": "Introductions"}],
            },
            {
                "unit_number": 7,
                "title": "Travel and Adventure",
                "topics": [{"topic_id": 2762, "title": "Travel plans"}],
            },
        ],
    },
}

students_page._render_teacher_program_assignment_list([row], "teacher_programs_student-1_english")
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))

    def test_two_program_tabs_with_matching_unit_names_render_without_duplicate_ids(self):
        app = AppTest.from_string(
            """
import streamlit as st
from helpers import learning_programs as programs

programs.load_assignment_progress_map = lambda _assignment_id: {}
programs.load_topic_video_links = lambda _program_ids: {}

english = {
    "id": 101,
    "title": "English Program",
    "units": [{"unit_number": 1, "title": "Introduction", "topics": []}],
}
spanish = {
    "id": 102,
    "title": "Spanish Program",
    "units": [{"unit_number": 1, "title": "Introduction", "topics": []}],
}

english_tab, spanish_tab = st.tabs(["English", "Spanish"])
with english_tab:
    programs.render_student_program_view(
        english,
        assignment_id=201,
        interactive=True,
        key_prefix="english_teacher-1_201",
    )
with spanish_tab:
    programs.render_student_program_view(
        spanish,
        assignment_id=202,
        interactive=True,
        key_prefix="spanish_teacher-1_202",
    )
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))

    def test_teacher_all_subject_tabs_render_matching_unit_names_without_duplicate_ids(self):
        app = AppTest.from_string(
            """
import streamlit as st
from app_pages import app_page_students as students_page

students_page.load_assignment_progress_map = lambda _assignment_id: {}
students_page.inject_resource_gallery_styles = lambda: None
students_page.extract_gallery_image_url = lambda _program: ""
students_page.render_gallery_card_html = lambda **kwargs: kwargs.get("title", "")
students_page._render_teacher_program_pagination = lambda *_args, **_kwargs: None

english_row = {
    "id": 201,
    "student_name": "Student",
    "subject_display": "English",
    "program": {
        "title": "English Program",
        "units": [{"unit_number": 1, "title": "Introduction", "topics": []}],
    },
}
spanish_row = {
    "id": 202,
    "student_name": "Student",
    "subject_display": "Spanish",
    "program": {
        "title": "Spanish Program",
        "units": [{"unit_number": 1, "title": "Introduction", "topics": []}],
    },
}

english_tab, spanish_tab = st.tabs(["English", "Spanish"])
with english_tab:
    students_page._render_teacher_program_assignment_list(
        [english_row],
        "teacher_programs_student-1_english",
    )
with spanish_tab:
    students_page._render_teacher_program_assignment_list(
        [spanish_row],
        "teacher_programs_student-1_spanish",
    )
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))

    def test_teacher_all_subject_recommendations_use_subject_assignment_scoped_widgets(self):
        app = AppTest.from_string(
            """
import streamlit as st
from app_pages import app_page_students as students_page

students_page.attach_teacher_objective_exposures = lambda rows, **_kwargs: rows
students_page._load_recommendation_resource_pool = lambda: []
students_page._load_assigned_resource_keys_for_student = lambda *_args, **_kwargs: set()
students_page._load_done_resource_keys_for_student = lambda *_args, **_kwargs: set()
students_page._inject_recommendation_styles = lambda: None

def recommendation_for_subject(*, selected_subject, **_kwargs):
    assignment_id = 201 if selected_subject == "english" else 202
    return ([{
        "title": "Introduction",
        "program_title": "Program",
        "subject_display": selected_subject.title(),
        "subject_key": selected_subject,
        "score": 0.8,
        "priority_label": "High",
        "focus_kind": "reinforce",
        "focus_label": "Reinforce",
        "objective": "Introduction",
        "reasons": [],
        "actions": [],
        "learning_program_assignment_id": assignment_id,
        "learning_program_topic_id": 1,
        "recommendation_bucket": "next_topic",
        "program_id": assignment_id,
    }], {"recent_score": None, "active_assignments": 0})

students_page._build_program_recommendations = recommendation_for_subject

program_rows = [
    {"id": 201, "subject_key": "english", "subject_display": "English", "program": {"subject": "english"}},
    {"id": 202, "subject_key": "spanish", "subject_display": "Spanish", "program": {"subject": "spanish"}},
]
students_page._render_recommendations_tab(
    [],
    program_rows,
    "__all__",
    "Student",
    {"student_id": "student-1"},
)
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))

    def test_teacher_done_resource_keys_exclude_assignment_attempts(self):
        from app_pages import app_page_students as students_page
        students_page = importlib.reload(students_page)

        class FilteringQuery:
            def __init__(self, rows):
                self.rows = list(rows)
                self.filters = []

            def select(self, *_args, **_kwargs):
                return self

            def eq(self, column, value):
                self.filters.append(("eq", column, value))
                return self

            def in_(self, column, values):
                self.filters.append(("in", column, set(values)))
                return self

            def order(self, *_args, **_kwargs):
                return self

            def limit(self, value):
                self.limit_value = value
                return self

            def execute(self):
                rows = self.rows
                for op, column, value in self.filters:
                    if op == "eq":
                        rows = [row for row in rows if str(row.get(column) or "") == str(value)]
                    elif op == "in":
                        rows = [row for row in rows if row.get(column) in value]
                return SimpleNamespace(data=rows[: getattr(self, "limit_value", len(rows))])

        class FilteringSupabase:
            def __init__(self):
                self.tables = {
                    "practice_sessions": [
                        {"id": 1, "user_id": "student-1", "source_type": "worksheet", "source_id": "42", "status": "completed"},
                        {"id": 2, "user_id": "student-1", "source_type": "exam", "source_id": "99", "status": "completed"},
                        {"id": 3, "user_id": "student-1", "source_type": "worksheet", "source_id": "77", "status": "in_progress"},
                    ],
                    "teacher_assignment_attempts": [
                        {"practice_session_id": 2, "student_id": "student-1"},
                    ],
                }

            def table(self, table_name):
                return FilteringQuery(self.tables.get(table_name, []))

        with patch.object(students_page, "get_sb", return_value=FilteringSupabase()):
            keys = students_page._load_done_resource_keys_for_student({"student_id": "student-1"})

        self.assertIn(("worksheet", "42"), keys)
        self.assertNotIn(("exam", "99"), keys)
        self.assertNotIn(("worksheet", "77"), keys)

    def test_teacher_recommendation_resource_card_shows_done_signal(self):
        app = AppTest.from_string(
            """
from app_pages import app_page_students as students_page

students_page.attach_teacher_resource_recommendation_exposures = lambda resources, **_kwargs: resources
students_page.render_learning_program_assign_dialog = lambda: None
students_page._recommended_resources_for_item = lambda *_args, **_kwargs: {
    "worksheet": [{
        "kind": "worksheet",
        "source": "own",
        "recommendation_bucket": "very_close",
        "row": {
            "id": 42,
            "title": "Fractions review",
            "subject": "english",
            "topic": "Fractions",
            "level_or_band": "A1",
        },
    }],
    "exam": [],
    "plan": [],
    "video": [],
}

students_page._render_recommended_resources_for_item(
    {
        "title": "Fractions",
        "objective": "Review fractions",
        "focus_kind": "reinforce",
        "subject_key": "english",
    },
    [],
    key_prefix="done_signal_test",
    assigned_resource_keys=set(),
    done_resource_keys={("worksheet", "42")},
)
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))
        rendered = "\n".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("classio-reco-resource-done", rendered)
        self.assertIn("Done", rendered)

    def test_resource_record_key_normalizes_float_ids_for_done_matching(self):
        from app_pages import app_page_students as students_page

        self.assertEqual(
            ("exam", "99"),
            students_page._resource_record_key("exam", 99.0),
        )

    def test_program_unit_expanders_have_invisible_assignment_scope(self):
        first = _scoped_expander_label("Unit 1: Introduction", "english:assignment-1")
        second = _scoped_expander_label("Unit 1: Introduction", "spanish:assignment-2")

        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith("Unit 1: Introduction"))
        self.assertTrue(second.startswith("Unit 1: Introduction"))

    def test_assignments_split_different_subjects_for_one_teacher(self):
        groups = _assignment_scope_groups(
            [
                {
                    "id": 1,
                    "subject_key": "english",
                    "subject_display": "English",
                    "teacher_id": "teacher-1",
                    "teacher_name": "Teacher A",
                },
                {
                    "id": 2,
                    "subject_key": "spanish",
                    "subject_display": "Spanish",
                    "teacher_id": "teacher-1",
                    "teacher_name": "Teacher A",
                },
            ]
        )

        self.assertEqual({"English", "Spanish"}, {group["label"] for group in groups})
        self.assertEqual(2, len(groups))

    def test_assignments_disambiguate_same_subject_from_two_teachers(self):
        groups = _assignment_scope_groups(
            [
                {
                    "id": 1,
                    "subject_key": "english",
                    "subject_display": "English",
                    "teacher_id": "teacher-1",
                    "teacher_name": "Teacher A",
                },
                {
                    "id": 2,
                    "subject_key": "english",
                    "subject_display": "English",
                    "teacher_id": "teacher-2",
                    "teacher_name": "Teacher B",
                },
            ]
        )

        self.assertEqual(
            {"English · Teacher A", "English · Teacher B"},
            {group["label"] for group in groups},
        )

    def test_programs_keep_same_subject_teacher_scopes_separate(self):
        groups = _program_subject_groups(
            [
                {
                    "id": 11,
                    "teacher_id": "teacher-1",
                    "teacher_name": "Teacher A",
                    "subject_display": "English",
                    "program": {"subject": "english"},
                },
                {
                    "id": 12,
                    "teacher_id": "teacher-2",
                    "teacher_name": "Teacher B",
                    "subject_display": "English",
                    "program": {"subject": "english"},
                },
            ]
        )

        self.assertEqual(2, len(groups))
        self.assertEqual(
            {"English · Teacher A", "English · Teacher B"},
            {label for _scope, label, _rows in groups},
        )

    def test_independent_history_and_progress_split_by_subject_only(self):
        frame = pd.DataFrame(
            [
                {"subject": "english", "topic": "Grammar"},
                {"subject": "english", "topic": "Reading"},
                {"subject": "spanish", "topic": "Vocabulario"},
            ]
        )

        groups = _practice_subject_groups(frame)

        self.assertEqual(2, len(groups))
        self.assertEqual(
            {"english_independent", "spanish_independent"},
            {key for key, _label, _frame in groups},
        )
        self.assertEqual(
            {"Grammar", "Reading"},
            set(groups[0][2]["topic"].tolist()),
        )

    def test_assignment_history_disambiguates_same_subject_by_teacher(self):
        frame = pd.DataFrame(
            [
                {
                    "subject": "english",
                    "topic": "Grammar",
                    "_scope_teacher_id": "teacher-1",
                    "_scope_teacher_name": "Teacher A",
                },
                {
                    "subject": "english",
                    "topic": "Reading",
                    "_scope_teacher_id": "teacher-2",
                    "_scope_teacher_name": "Teacher B",
                },
            ]
        )

        groups = _practice_subject_groups(frame)

        self.assertEqual(
            {"English · Teacher A", "English · Teacher B"},
            {label for _key, label, _frame in groups},
        )

    def test_student_practice_history_and_progress_tolerate_nullable_scope_ids(self):
        app = AppTest.from_string(
            """
import pandas as pd
from app_pages import student_practice as practice

practice.load_assignment_state_map = lambda _assignment_ids: {}
practice.load_student_assignments = lambda: []

history = pd.DataFrame([
    {
        "id": float("nan"),
        "source_id": float("nan"),
        "source_type": "worksheet",
        "title": "Practice",
        "score_pct": 80,
        "total_questions": 5,
        "correct_count": 4,
        "xp_earned": 10,
        "best_streak": 2,
        "created_at": "2026-07-23T09:00:00",
        "subject": "english",
        "topic": "Grammar",
    }
])
progress = pd.DataFrame([
    {
        "id": 1,
        "assignment_id": float("nan"),
        "subject": "english",
        "topic": "Grammar",
        "exercise_type": "multiple_choice",
        "accuracy_pct": 75,
        "total_attempted": 4,
        "total_correct": 3,
        "total_xp": 10,
    }
])

practice._render_history_tab(history)
practice._render_progress_tab(progress)
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))

    def test_student_progress_uses_resource_color_separate_from_result_color(self):
        app = AppTest.from_string(
            """
import pandas as pd
from app_pages import student_practice as practice

practice.load_student_assignments = lambda: []

progress = pd.DataFrame([
    {
        "id": 1,
        "assignment_id": 10,
        "source_type": "exam",
        "subject": "english",
        "topic": "Grammar",
        "exercise_type": "multiple_choice",
        "accuracy_pct": 55,
        "total_attempted": 4,
        "total_correct": 2,
        "total_xp": 5,
    }
])

practice._render_progress_tab(progress)
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))
        rendered = "\\n".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("--practice-resource-accent:#ec4899", rendered)
        self.assertNotIn("Smart Practice", rendered)
        self.assertNotIn("🧩 Exam", rendered)
        self.assertIn("background:#EF4444", rendered)

    def test_student_progress_infers_resource_color_from_assignment_when_progress_is_legacy(self):
        app = AppTest.from_string(
            """
import pandas as pd
from app_pages import student_practice as practice

practice.load_student_assignments = lambda: [
    {"id": 10, "assignment_type": "worksheet", "teacher_id": "teacher-1", "teacher_name": "Teacher A"}
]
practice.load_practice_progress = lambda: pd.DataFrame([
    {
        "id": 1,
        "assignment_id": 10,
        "source_type": "custom",
        "subject": "english",
        "topic": "Grammar",
        "exercise_type": "multiple_choice",
        "accuracy_pct": 86,
        "total_attempted": 7,
        "total_correct": 6,
        "total_xp": 41,
        "scope_key": "assignment:10",
    }
])
practice.load_practice_history = lambda limit=500: pd.DataFrame()

practice._render_progress_tab()
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))
        rendered = "\\n".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("--practice-resource-accent:#8b5cf6", rendered)
        self.assertNotIn("Smart Practice", rendered)

    def test_shared_resource_kind_colors_are_canonical(self):
        self.assertEqual("#8b5cf6", resource_kind_accent("worksheet"))
        self.assertEqual("#ec4899", resource_kind_accent("exam_builder"))
        self.assertEqual("#1e3a8a", resource_kind_accent("video_library"))
        self.assertEqual("#60a5fa", resource_kind_accent("learning_program"))
        self.assertEqual("#eab308", resource_kind_accent("lesson_plan_topic"))
        self.assertEqual("#eab308", resource_kind_accent("lesson_plan"))

    def test_video_progress_renders_as_engagement_not_correctness(self):
        app = AppTest.from_string(
            """
import pandas as pd
from app_pages import student_practice as practice

practice.load_student_assignments = lambda: []

progress = pd.DataFrame([
    {
        "id": 1,
        "assignment_id": 10,
        "source_type": "video",
        "subject": "english",
        "topic": "Daily routine",
        "exercise_type": "video_watch",
        "accuracy_pct": 0,
        "total_attempted": 2,
        "total_correct": 0,
        "total_xp": 0,
    }
])

practice._render_progress_tab(progress)
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))
        rendered = "\\n".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("--practice-resource-accent:#1e3a8a", rendered)
        self.assertIn("Watched", rendered)
        self.assertIn("Views", rendered)
        self.assertNotIn("2 questions attempted", rendered)

    def test_recommended_worksheet_open_failure_shows_friendly_message(self):
        app = AppTest.from_string(
            """
from app_pages import student_practice as practice
import helpers.worksheet_storage as worksheet_storage

def fail_load(_worksheet_id):
    raise RuntimeError("raw supabase/httpx traceback")

worksheet_storage.load_worksheet_record = fail_load
practice.log_student_recommendation_open = lambda *_args, **_kwargs: None
practice.load_student_assignment_by_id = lambda _assignment_id: {}
practice.st.session_state["_start_sp_reco_english_worksheet_7_0_0"] = True

practice._render_recommendation_subject_group(
    [
        {
            "resource_type": "worksheet",
            "id": 7,
            "title": "Fractions review",
            "subject": "english",
            "topic": "Fractions",
            "level": "A1",
            "exercise_type": "multiple_choice",
            "row": {"id": 7, "title": "Fractions review", "subject": "english", "topic": "Fractions"},
        }
    ],
    group_key="english",
)
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))
        rendered_errors = "\n".join(str(error.value) for error in app.error)
        self.assertIn("couldn't open this practice activity", rendered_errors)
        self.assertNotIn("raw supabase/httpx traceback", rendered_errors)

    def test_practice_card_uses_full_record_image_when_list_row_is_lightweight(self):
        app = AppTest.from_string(
            """
from types import SimpleNamespace
from app_pages import student_practice as practice

class Query:
    def select(self, *_args, **_kwargs):
        return self
    def eq(self, *_args, **_kwargs):
        return self
    def limit(self, *_args, **_kwargs):
        return self
    def execute(self):
        return SimpleNamespace(data=[{
            "id": 7,
            "worksheet_json": {
                "title": "Image worksheet",
                "visual_supports": [{"image_url": "https://example.com/card-image.png"}],
            },
        }])

class Supabase:
    def table(self, name):
        assert name == "worksheets"
        return Query()

practice.get_sb = lambda: Supabase()
practice._render_practice_card(
    title="Image worksheet",
    subject="english",
    topic="Images",
    level="A1",
    ws_type="multiple_choice",
    btn_key="image_card",
    row={"id": 7, "title": "Image worksheet", "subject": "english", "topic": "Images"},
    resource_type="worksheet",
)
"""
        ).run(timeout=10)

        self.assertEqual([], list(app.exception))
        rendered = "\n".join(str(markdown.value) for markdown in app.markdown)
        self.assertIn("https://example.com/card-image.png", rendered)


if __name__ == "__main__":
    unittest.main()
