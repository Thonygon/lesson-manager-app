import unittest
from unittest.mock import patch

from app_pages import student_home


class StudentHomeResilienceTests(unittest.TestCase):
    def test_recommendations_fall_back_to_empty_when_a_source_fails(self):
        with (
            patch.object(student_home, "user_has_feature", return_value=True),
            patch.object(student_home, "load_public_worksheets", side_effect=RuntimeError("worksheets down")),
            patch.object(student_home, "load_public_exams", return_value="exams"),
            patch.object(student_home, "load_public_videos", return_value="videos"),
            patch.object(student_home, "build_recommended_materials", return_value=["ok"]) as build_mock,
        ):
            recommended = student_home._load_student_home_recommendations("student-1")

        self.assertEqual(["ok"], recommended)
        build_mock.assert_called_once_with(
            None,
            "exams",
            "videos",
            limit=3,
        )

    def test_recommendations_fall_back_to_empty_when_builder_fails(self):
        with (
            patch.object(student_home, "user_has_feature", return_value=False),
            patch.object(student_home, "load_public_worksheets", return_value="worksheets"),
            patch.object(student_home, "load_public_exams", return_value="exams"),
            patch.object(student_home, "build_recommended_materials", side_effect=RuntimeError("builder down")),
        ):
            recommended = student_home._load_student_home_recommendations("student-1")

        self.assertEqual([], recommended)


if __name__ == "__main__":
    unittest.main()
