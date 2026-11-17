"""The comparator answers two independent questions and must not let one hide the other."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from compare import compare_tellings


def finding_line(index, key, text):
    return {"index": index, "text": text, "finding_key": key, "declared_class": None}


def furniture_line(index, declared_class, text):
    return {"index": index, "text": text, "finding_key": None, "declared_class": declared_class}


class CompareTellingsTest(unittest.TestCase):
    def test_missing_finding_is_reported_on_the_finding_axis(self):
        fuller = {
            "b1": [
                finding_line(
                    1, "F35.controls", "1) The controls sit under the board, not beside it."
                ),
                finding_line(2, "F37.space", "2) There is no space to the right of the board."),
            ]
        }
        thinner = {
            "b1": [
                finding_line(
                    1, "F35.controls", "1) The controls sit under the board, not beside it."
                )
            ]
        }
        result = compare_tellings(thinner, fuller)
        self.assertEqual(len(result["finding_missing"]), 1)
        missing = result["finding_missing"][0]
        self.assertEqual(missing["finding_key"], "F37.space")
        self.assertFalse(missing["declared"])

    def test_text_only_change_is_reported_on_the_word_axis(self):
        left = {"b1": [finding_line(1, "F05", "1) The board does not appear when the game opens.")]}
        right = {"b1": [finding_line(1, "F05", "1) The board never appears when the game opens.")]}
        result = compare_tellings(left, right)
        self.assertEqual(len(result["word_differences"]), 1)
        self.assertFalse(result["word_differences"][0]["declared"])
        self.assertEqual(
            len(result["finding_missing"])
            + len(result["finding_extra"])
            + len(result["finding_reordered"]),
            0,
        )

    def test_declared_furniture_is_declared_not_undeclared(self):
        left = {"b1": [furniture_line(1, "section-headers", "PROBLEM: The game is not finished.")]}
        right = {"b1": [furniture_line(1, "section-headers", "PROBLEM: The game is unfinished.")]}
        result = compare_tellings(left, right)
        self.assertEqual(result["undeclared_count"], 0)
        self.assertEqual(result["declared_count"], 1)


if __name__ == "__main__":
    unittest.main()
