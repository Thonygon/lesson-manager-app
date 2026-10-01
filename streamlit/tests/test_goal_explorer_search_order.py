import unittest
from unittest.mock import patch

import pandas as pd

from helpers import goal_explorer


class GoalExplorerSearchOrderTests(unittest.TestCase):
    def test_query_results_keep_rank_search_order_instead_of_recency_order(self):
        ranked = pd.DataFrame(
            [
                {
                    "title": "Exact older match",
                    "created_at": "2026-08-01T10:00:00",
                    "_search_subject": "English",
                },
                {
                    "title": "Looser newer match",
                    "created_at": "2026-08-10T10:00:00",
                    "_search_subject": "English",
                },
            ]
        )

        with (
            patch.object(goal_explorer, "_rank_search", return_value=ranked.copy()) as rank_search,
            patch.object(goal_explorer, "t", side_effect=lambda value: value),
        ):
            filtered = goal_explorer._apply_explore_shared_filters(
                ranked.copy(),
                query="family",
                subject_filter="all",
                stage_filter="all",
                level_filter="all",
                weights={"title": 6},
            )

        rank_search.assert_called_once()
        self.assertEqual(
            ["Exact older match", "Looser newer match"],
            filtered["title"].tolist(),
        )

    def test_no_query_results_fall_back_to_recency_order(self):
        base = pd.DataFrame(
            [
                {"title": "Older item", "created_at": "2026-08-01T10:00:00", "_search_subject": "English"},
                {"title": "Newer item", "created_at": "2026-08-10T10:00:00", "_search_subject": "English"},
            ]
        )

        with patch.object(goal_explorer, "t", side_effect=lambda value: value):
            filtered = goal_explorer._apply_explore_shared_filters(
                base.copy(),
                query="",
                subject_filter="all",
                stage_filter="all",
                level_filter="all",
                weights={"title": 6},
            )

        self.assertEqual(
            ["Newer item", "Older item"],
            filtered["title"].tolist(),
        )


if __name__ == "__main__":
    unittest.main()
