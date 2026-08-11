#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Run real PostgreSQL telemetry loads and capture query plans")
    parser.add_argument("--sizes", type=int, nargs="+", default=[10000, 100000])
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/postgres-report.json"))
    args = parser.parse_args()
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise SystemExit("DATABASE_URL is required; no synthetic PostgreSQL result will be produced")
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise SystemExit("Install requirements.txt before running PostgreSQL benchmark") from exc

    loads = []
    for size in args.sizes:
        command = [sys.executable, "scripts/load_test.py", "--events", str(size), "--workers", str(args.workers)]
        completed = subprocess.run(command, text=True, capture_output=True, check=True, env=os.environ)
        loads.append({"events": size, "output": completed.stdout.strip()})

    queries = {
        "device_history": "select * from telemetry where device_id='load-00' order by measured_at desc,id desc limit 100",
        "active_alerts": "select a.id,a.status,t.device_id,t.measured_at from alerts a join telemetry t on t.id=a.telemetry_id where a.status!='resolved' order by a.id desc limit 100",
        "anomaly_history": "select * from telemetry where is_anomaly order by measured_at desc,id desc limit 100",
    }
    plans = {}
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        for name, query in queries.items():
            plan = connection.execute(f"explain (analyze, buffers, format json) {query}").fetchone()["QUERY PLAN"]
            plans[name] = plan
    report = {"measured_at": datetime.now(timezone.utc).isoformat(), "database": "postgresql",
              "loads": loads, "query_plans": plans, "evidence": "measured"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str))
    print(args.output)


if __name__ == "__main__": main()
