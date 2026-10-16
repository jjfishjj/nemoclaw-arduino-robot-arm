from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from portable_trainer.checkpoints import find_latest_complete_checkpoint


class CheckpointTests(unittest.TestCase):
    def test_selects_highest_complete_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "checkpoint-2").mkdir()
            incomplete = root / "checkpoint-10"
            incomplete.mkdir()
            (incomplete / "checkpoint-is-incomplete.txt").touch()
            latest = root / "checkpoint-7"
            latest.mkdir()
            self.assertEqual(find_latest_complete_checkpoint(root), latest)

    def test_prefers_hub_last_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "checkpoint-20").mkdir()
            hub = root / "last-checkpoint"
            hub.mkdir()
            (hub / "trainer_state.json").write_text("{}", encoding="utf-8")
            self.assertEqual(find_latest_complete_checkpoint(root), hub)


if __name__ == "__main__":
    unittest.main()
