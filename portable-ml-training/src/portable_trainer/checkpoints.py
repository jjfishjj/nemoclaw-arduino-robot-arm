from __future__ import annotations

import re
from pathlib import Path

CHECKPOINT_PATTERN = re.compile(r"^checkpoint-(\d+)$")
INCOMPLETE_SENTINEL = "checkpoint-is-incomplete.txt"


def checkpoint_step(path: Path) -> int | None:
    match = CHECKPOINT_PATTERN.match(path.name)
    return int(match.group(1)) if match else None


def find_latest_complete_checkpoint(output_dir: str | Path) -> Path | None:
    root = Path(output_dir)
    if not root.exists():
        return None
    hub_checkpoint = root / "last-checkpoint"
    if (
        hub_checkpoint.is_dir()
        and (hub_checkpoint / "trainer_state.json").exists()
        and not (hub_checkpoint / INCOMPLETE_SENTINEL).exists()
    ):
        return hub_checkpoint
    candidates: list[tuple[int, Path]] = []
    for child in root.iterdir():
        step = checkpoint_step(child)
        if step is None or not child.is_dir():
            continue
        if (child / INCOMPLETE_SENTINEL).exists():
            continue
        candidates.append((step, child))
    return max(candidates, default=(0, None), key=lambda item: item[0])[1]


def resolve_resume_checkpoint(config: dict, output_dir: str | Path) -> Path | None:
    mode = str(config["resume"]["mode"])
    if mode == "never":
        return None
    if mode.startswith("path:"):
        path = Path(mode.removeprefix("path:")).expanduser()
        if not path.is_dir():
            raise FileNotFoundError(f"Requested checkpoint does not exist: {path}")
        return path
    return find_latest_complete_checkpoint(output_dir)
