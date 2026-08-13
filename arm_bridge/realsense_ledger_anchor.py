"""Create and verify an attestation-ready anchor for the baseline ledger head."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .core import SafetyError
from .realsense_baseline_ledger import artifact_digest, load_ledger


ANCHOR_SCHEMA = "realsense-baseline-ledger-anchor/v1"


def _ledger_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise SafetyError(f"cannot read ledger: {exc}") from exc


def create_anchor(ledger_path: Path, baseline_path: Path, *, workflow_run: str,
                  commit_sha: str, occurred_at: str) -> dict:
    entries = load_ledger(ledger_path)
    if not entries:
        raise SafetyError("cannot anchor an empty ledger")
    try:
        baseline_sha256 = artifact_digest(baseline_path.read_bytes())
    except OSError as exc:
        raise SafetyError(f"cannot read active baseline: {exc}") from exc
    head = entries[-1]
    if baseline_sha256 != head["baseline_sha256"]:
        raise SafetyError("active baseline digest differs from the ledger head")
    if not workflow_run or len(commit_sha) != 40 or not occurred_at:
        raise SafetyError("anchor provenance is malformed")
    return {
        "schema_version": ANCHOR_SCHEMA,
        "ledger_entries": len(entries),
        "ledger_head_sha256": head["entry_sha256"],
        "ledger_sha256": _ledger_sha256(ledger_path),
        "baseline_sha256": baseline_sha256,
        "ledger_action": head["action"],
        "workflow_run": workflow_run,
        "commit_sha": commit_sha,
        "occurred_at": occurred_at,
        "motion_enabled": False,
    }


def verify_anchor(anchor: dict, ledger_path: Path, baseline_path: Path) -> dict:
    if anchor.get("schema_version") != ANCHOR_SCHEMA:
        raise SafetyError("ledger anchor schema is unsupported")
    if anchor.get("motion_enabled") is not False:
        raise SafetyError("ledger anchor must explicitly keep motion disabled")
    if (not isinstance(anchor.get("workflow_run"), str) or not anchor["workflow_run"] or
            not isinstance(anchor.get("commit_sha"), str) or len(anchor["commit_sha"]) != 40 or
            not isinstance(anchor.get("occurred_at"), str) or not anchor["occurred_at"]):
        raise SafetyError("ledger anchor provenance is malformed")
    entries = load_ledger(ledger_path)
    if anchor.get("ledger_entries") != len(entries):
        raise SafetyError("ledger length differs from the trusted anchor")
    if not entries or anchor.get("ledger_head_sha256") != entries[-1]["entry_sha256"]:
        raise SafetyError("ledger head differs from the trusted anchor")
    if anchor.get("ledger_action") != entries[-1]["action"]:
        raise SafetyError("ledger action differs from the trusted anchor")
    if anchor.get("ledger_sha256") != _ledger_sha256(ledger_path):
        raise SafetyError("ledger bytes differ from the trusted anchor")
    try:
        baseline_sha256 = artifact_digest(baseline_path.read_bytes())
    except OSError as exc:
        raise SafetyError(f"cannot read active baseline: {exc}") from exc
    if anchor.get("baseline_sha256") != baseline_sha256:
        raise SafetyError("active baseline differs from the trusted anchor")
    return {"ok": True, "ledger_entries": len(entries),
            "ledger_head_sha256": entries[-1]["entry_sha256"],
            "baseline_sha256": baseline_sha256, "motion_enabled": False}


def _load_anchor(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SafetyError(f"cannot load ledger anchor: {exc}") from exc
    if not isinstance(value, dict):
        raise SafetyError("ledger anchor must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or verify a RealSense ledger anchor")
    parser.add_argument("action", choices=("create", "verify", "verify-or-bootstrap"))
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--anchor", type=Path, required=True)
    parser.add_argument("--workflow-run", default="")
    parser.add_argument("--commit-sha", default="")
    parser.add_argument("--occurred-at", default="")
    args = parser.parse_args(argv)
    try:
        if args.action == "create":
            result = create_anchor(args.ledger, args.baseline, workflow_run=args.workflow_run,
                                   commit_sha=args.commit_sha, occurred_at=args.occurred_at)
            args.anchor.parent.mkdir(parents=True, exist_ok=True)
            args.anchor.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        elif args.action == "verify-or-bootstrap" and not args.anchor.exists():
            if load_ledger(args.ledger):
                raise SafetyError("non-empty ledger is missing its trusted anchor")
            result = {"ok": True, "bootstrap": True, "motion_enabled": False}
        else:
            result = verify_anchor(_load_anchor(args.anchor), args.ledger, args.baseline)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except SafetyError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
