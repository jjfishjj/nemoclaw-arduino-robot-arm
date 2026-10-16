from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(PROJECT_DIR / "src"))

from portable_trainer.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sample = json.loads(
            (PROJECT_DIR / "configs" / "qlora-smoke.json").read_text(encoding="utf-8")
        )

    def write(self, config: dict) -> Path:
        temp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(config, temp)
        temp.close()
        self.addCleanup(lambda: os.unlink(temp.name))
        return Path(temp.name)

    def test_valid_sample_loads(self) -> None:
        config = load_config(PROJECT_DIR / "configs" / "qlora-smoke.json")
        self.assertEqual(config["method"]["type"], "qlora")

    def test_hub_target_environment_enables_push(self) -> None:
        with patch.dict(os.environ, {"HF_MODEL_ID": "demo/output"}, clear=False):
            config = load_config(self.write(self.sample))
        self.assertTrue(config["output"]["push_to_hub"])
        self.assertEqual(config["output"]["hub_model_id"], "demo/output")

    def test_requires_dataset_text_or_pair(self) -> None:
        self.sample["dataset"]["text_field"] = None
        self.sample["dataset"]["prompt_field"] = None
        self.sample["dataset"]["response_field"] = None
        with self.assertRaises(ConfigError):
            load_config(self.write(self.sample))

    def test_qlora_requires_four_bit(self) -> None:
        self.sample["method"]["load_in_4bit"] = False
        with self.assertRaises(ConfigError):
            load_config(self.write(self.sample))


if __name__ == "__main__":
    unittest.main()
