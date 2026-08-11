#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Delete expired telemetry and benchmark data")
    parser.add_argument("--days", type=int, default=int(os.getenv("RETENTION_DAYS", "30")))
    parser.add_argument("--output", type=Path, default=Path("data/retention-last-run.json"))
    args = parser.parse_args()
    if not 1 <= args.days <= 3650:
        raise SystemExit("retention days must be between 1 and 3650")
    database_url = os.getenv("DATABASE_URL")
    database_url_file = os.getenv("DATABASE_URL_FILE")
    if not database_url and database_url_file:
        database_url = Path(database_url_file).read_text().strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is required; retention was not executed")
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install requirements.txt before running retention") from exc

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    with psycopg.connect(database_url) as connection:
        telemetry_deleted = connection.execute(
            "delete from telemetry where measured_at < %s", (cutoff,)
        ).rowcount
        benchmarks_deleted = connection.execute(
            "delete from benchmark_runs where measured_at < %s", (cutoff,)
        ).rowcount
        connection.execute(
            "insert into retention_runs(cutoff,telemetry_deleted,benchmark_runs_deleted) values(%s,%s,%s)",
            (cutoff, telemetry_deleted, benchmarks_deleted),
        )
    report = {
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "cutoff": cutoff.isoformat(),
        "retention_days": args.days,
        "telemetry_deleted": telemetry_deleted,
        "benchmark_runs_deleted": benchmarks_deleted,
        "evidence": "measured",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
