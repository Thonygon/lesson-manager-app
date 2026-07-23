import unittest

from helpers.recommendation_memory import (
    clear_active_recommendation_context,
    recommendation_context_for_assignment,
    set_active_recommendation_context,
)
from helpers import student_recommendations as recommendations


class StudentRecommendationScopingTests(unittest.TestCase):
    def test_balancing_keeps_each_active_subject_in_the_feed(self):
        rows = [
            {
                "id": 1,
                "subject": "english",
                "score": 0.99,
                "learning_program_assignment_id": 101,
            },
            {
                "id": 2,
                "subject": "english",
                "score": 0.95,
                "learning_program_assignment_id": 101,
            },
            {
                "id": 3,
                "subject": "spanish",
                "score": 0.62,
                "learning_program_assignment_id": 102,
            },
        ]

        selected = recommendations._select_subject_balanced_recommendations(
            rows,
            {"assignment:101", "assignment:102"},
            limit=2,
        )

        self.assertEqual({"english", "spanish"}, {row["subject"] for row in selected})

    def test_resource_scope_uses_subject_assignment_not_teacher_identity(self):
        program_signals = {
            "program_scopes": {
                "english": [
                    {
                        "learning_program_assignment_id": 101,
                        "program_id": 201,
                        "topics": [
                            {
                                "topic_id": 301,
                                "tokens": {"alphabet", "vocabulary"},
                                "is_complete": False,
                                "position": 1,
                            }
                        ],
                    }
                ],
                "spanish": [
                    {
                        "learning_program_assignment_id": 102,
                        "program_id": 202,
                        "topics": [
                            {
                                "topic_id": 302,
                                "tokens": {"alfabeto", "vocabulario"},
                                "is_complete": False,
                                "position": 1,
                            }
                        ],
                    }
                ],
            }
        }

        english_scope = recommendations._program_scopes_for_resource(
            {"subject": "english", "topic": "Alphabet vocabulary"},
            program_signals,
            None,
        )[0]
        spanish_scope = recommendations._program_scopes_for_resource(
            {"subject": "spanish", "topic": "Alfabeto y vocabulario"},
            program_signals,
            None,
        )[0]

        self.assertEqual(101, english_scope["learning_program_assignment_id"])
        self.assertEqual(301, english_scope["learning_program_topic_id"])
        self.assertEqual(102, spanish_scope["learning_program_assignment_id"])
        self.assertEqual(302, spanish_scope["learning_program_topic_id"])

    def test_exact_assignment_scope_wins_for_teacher_assigned_resource(self):
        program_signals = {
            "program_scopes": {
                "english": [
                    {
                        "learning_program_assignment_id": 101,
                        "program_id": 201,
                        "topics": [],
                    }
                ]
            }
        }
        assignment_state = {
            "learning_program_assignment_id": 150,
            "learning_program_topic_id": 350,
        }

        scope = recommendations._program_scopes_for_resource(
            {"subject": "english", "topic": "Grammar"},
            program_signals,
            assignment_state,
        )[0]

        self.assertEqual(150, scope["learning_program_assignment_id"])
        self.assertEqual(350, scope["learning_program_topic_id"])

    def test_same_subject_from_two_teachers_gets_distinct_tab_labels(self):
        groups = recommendations.group_recommendations_for_subject_tabs(
            [
                {
                    "id": 1,
                    "subject": "english",
                    "subject_display": "English",
                    "program_teacher_name": "Teacher A",
                    "learning_program_assignment_id": 101,
                },
                {
                    "id": 2,
                    "subject": "english",
                    "subject_display": "English",
                    "program_teacher_name": "Teacher B",
                    "learning_program_assignment_id": 102,
                },
            ]
        )

        self.assertEqual(
            {"English · Teacher A", "English · Teacher B"},
            {group["label"] for group in groups},
        )

    def test_different_subjects_keep_subject_only_tab_labels(self):
        groups = recommendations.group_recommendations_for_subject_tabs(
            [
                {
                    "id": 1,
                    "subject": "english",
                    "subject_display": "English",
                    "program_teacher_name": "Teacher A",
                    "learning_program_assignment_id": 101,
                },
                {
                    "id": 2,
                    "subject": "spanish",
                    "subject_display": "Spanish",
                    "program_teacher_name": "Teacher A",
                    "learning_program_assignment_id": 102,
                },
            ]
        )

        self.assertEqual({"English", "Spanish"}, {group["label"] for group in groups})

    def test_assignment_recommendation_context_requires_matching_topic(self):
        try:
            set_active_recommendation_context(
                {
                    "student_id": "student-1",
                    "subject_key": "english",
                    "title": "Travel plans",
                    "learning_program_assignment_id": 201,
                    "learning_program_topic_id": 301,
                }
            )

            matched = recommendation_context_for_assignment(
                link={"student_id": "student-1"},
                subject_scope={"subject_key": "english"},
                topic_text="Travel plans",
            )
            mismatched = recommendation_context_for_assignment(
                link={"student_id": "student-1"},
                subject_scope={"subject_key": "english"},
                topic_text="Airport vocabulary",
            )
        finally:
            clear_active_recommendation_context()

        self.assertEqual(201, matched["learning_program_assignment_id"])
        self.assertEqual({}, mismatched)


if __name__ == "__main__":
    unittest.main()
