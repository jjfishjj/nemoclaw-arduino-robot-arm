"""Append-only digest ledger and rollback preparation for RealSense baselines."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from .core import SafetyError
from .realsense_baseline_promotion import validate_baseline_candidate


LEDGER_SCHEMA = "realsense-baseline-ledger/v1"
DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def artifact_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _entry_digest(entry: dict) -> str:
    unsigned = {key: value for key, value in entry.items() if key != "entry_sha256"}
    encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    entries = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SafetyError(f"ledger line {line_number} is invalid JSON") from exc
        if not isinstance(entry, dict):
            raise SafetyError(f"ledger line {line_number} must be an object")
        entries.append(entry)
    validate_ledger(entries)
    return entries


def validate_ledger(entries: list[dict]) -> None:
    previous = None
    known_promotions: set[str] = set()
    for index, entry in enumerate(entries):
        if entry.get("schema_version") != LEDGER_SCHEMA:
            raise SafetyError(f"ledger entry {index} schema is unsupported")
        if entry.get("sequence") != index + 1:
            raise SafetyError(f"ledger entry {index} sequence is broken")
        if entry.get("previous_entry_sha256") != previous:
            raise SafetyError(f"ledger entry {index} hash chain is broken")
        digest = entry.get("baseline_sha256")
        if not isinstance(digest, str) or not DIGEST_RE.fullmatch(digest):
            raise SafetyError(f"ledger entry {index} baseline digest is malformed")
        action = entry.get("action")
        if action not in {"PROMOTE", "ROLLBACK"}:
            raise SafetyError(f"ledger entry {index} action is unsupported")
        if action == "PROMOTE":
            known_promotions.add(digest)
        elif digest not in known_promotions:
            raise SafetyError(f"ledger entry {index} rolls back to an unknown promotion")
        if entry.get("motion_enabled") is not False:
            raise SafetyError(f"ledger entry {index} must keep motion disabled")
        expected = _entry_digest(entry)
        if entry.get("entry_sha256") != expected:
            raise SafetyError(f"ledger entry {index} digest is invalid")
        previous = expected


def append_entry(entries: list[dict], *, action: str, baseline_sha256: str,
                 occurred_at: str, actor: str, workflow_run: str, reason: str = "") -> dict:
    validate_ledger(entries)
    if action not in {"PROMOTE", "ROLLBACK"}:
        raise SafetyError("ledger action is unsupported")
    if not DIGEST_RE.fullmatch(baseline_sha256):
        raise SafetyError("baseline digest is malformed")
    if action == "ROLLBACK" and baseline_sha256 not in {
        entry["baseline_sha256"] for entry in entries if entry["action"] == "PROMOTE"
    }:
        raise SafetyError("rollback target was never promoted")
    if not occurred_at or not actor or not workflow_run:
        raise SafetyError("ledger provenance fields are required")
    entry = {
        "schema_version": LEDGER_SCHEMA,
        "sequence": len(entries) + 1,
        "action": action,
        "baseline_sha256": baseline_sha256,
        "previous_entry_sha256": entries[-1]["entry_sha256"] if entries else None,
        "occurred_at": occurred_at,
        "actor": actor,
        "workflow_run": workflow_run,
        "reason": reason,
        "motion_enabled": False,
    }
    entry["entry_sha256"] = _entry_digest(entry)
    entries.append(entry)
    validate_ledger(entries)
    return entry


def write_ledger(path: Path, entries: list[dict]) -> None:
    validate_ledger(entries)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries), encoding="utf-8")


def _validated_artifact(path: Path) -> tuple[bytes, str]:
    try:
        data = path.read_bytes()
        candidate = json.loads(data)
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"cannot load baseline artifact: {exc}") from exc
    if not isinstance(candidate, dict):
        raise SafetyError("baseline artifact must be a JSON object")
    receipt = validate_baseline_candidate(candidate, data)
    return data, receipt["artifact_sha256"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintain the append-only RealSense baseline ledger")
    parser.add_argument("action", choices=("promote", "rollback", "verify"))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--target", type=Path)
    parser.add_argument("--digest")
    parser.add_argument("--occurred-at", default="")
    parser.add_argument("--actor", default="")
    parser.add_argument("--workflow-run", default="")
    parser.add_argument("--reason", default="")
    args = parser.parse_args(argv)
    try:
        entries = load_ledger(args.ledger)
        if args.action == "verify":
            print(json.dumps({"ok": True, "entries": len(entries), "motion_enabled": False}))
            return 0
        if not args.archive_dir or not args.target:
            raise SafetyError("--archive-dir and --target are required")
        if args.action == "promote":
            if not args.artifact:
                raise SafetyError("--artifact is required for promotion")
            data, digest = _validated_artifact(args.artifact)
            archive = args.archive_dir / f"{digest}.json"
            if archive.exists() and archive.read_bytes() != data:
                raise SafetyError("archived digest collision")
            archive.parent.mkdir(parents=True, exist_ok=True)
            archive.write_bytes(data)
            args.target.parent.mkdir(parents=True, exist_ok=True)
            args.target.write_bytes(data)
            action = "PROMOTE"
        else:
            digest = (args.digest or "").lower()
            if not DIGEST_RE.fullmatch(digest):
                raise SafetyError("--digest must be a SHA-256 value")
            if digest not in {
                entry["baseline_sha256"] for entry in entries if entry["action"] == "PROMOTE"
            }:
                raise SafetyError("rollback target was never promoted")
            archive = args.archive_dir / f"{digest}.json"
            data, actual = _validated_artifact(archive)
            if actual != digest:
                raise SafetyError("rollback archive digest does not match its filename")
            args.target.parent.mkdir(parents=True, exist_ok=True)
            args.target.write_bytes(data)
            action = "ROLLBACK"
        entry = append_entry(entries, action=action, baseline_sha256=digest,
                             occurred_at=args.occurred_at, actor=args.actor,
                             workflow_run=args.workflow_run, reason=args.reason)
        write_ledger(args.ledger, entries)
        print(json.dumps(entry, indent=2, sort_keys=True))
        return 0
    except SafetyError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
