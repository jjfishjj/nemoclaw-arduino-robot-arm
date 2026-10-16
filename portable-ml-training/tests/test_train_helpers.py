from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
TRAIN_PATH = PROJECT_DIR / "src" / "train.py"
spec = importlib.util.spec_from_file_location("portable_train", TRAIN_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TrainHelperTests(unittest.TestCase):
    def test_text_record(self) -> None:
        self.assertEqual(module.format_record({"text": "hello"}, {"text_field": "text"}), "hello")

    def test_prompt_response_record(self) -> None:
        result = module.format_record(
            {"instruction": "Add", "output": "Four"},
            {"text_field": None, "prompt_field": "instruction", "response_field": "output"},
        )
        self.assertIn("### Instruction\nAdd", result)
        self.assertIn("### Response\nFour", result)

    def test_empty_text_fails_early(self) -> None:
        with self.assertRaises(ValueError):
            module.format_record({"text": ""}, {"text_field": "text"})


if __name__ == "__main__":
    unittest.main()
