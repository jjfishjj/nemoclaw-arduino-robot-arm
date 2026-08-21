#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def summarize_plan(raw_plan: list[dict]) -> dict:
    root = raw_plan[0]
    nodes: list[str] = []

    def visit(node: dict) -> None:
        nodes.append(node.get("Node Type", "unknown"))
        for child in node.get("Plans", []):
            visit(child)

    visit(root["Plan"])
    return {
        "planning_ms": root.get("Planning Time"),
        "execution_ms": root.get("Execution Time"),
        "nodes": nodes,
        "shared_hit_blocks": root["Plan"].get("Shared Hit Blocks", 0),
        "shared_read_blocks": root["Plan"].get("Shared Read Blocks", 0),
    }


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
        connection.execute("analyze telemetry")
        connection.execute("analyze alerts")
        for name, query in queries.items():
            plan = connection.execute(f"explain (analyze, buffers, format json) {query}").fetchone()["QUERY PLAN"]
            plans[name] = {"summary": summarize_plan(plan), "raw": plan}
        maintenance = connection.execute(
            """select relname,last_analyze,last_autoanalyze,n_live_tup,n_dead_tup
               from pg_stat_user_tables
               where relname in ('telemetry','alerts','benchmark_runs') order by relname"""
        ).fetchall()
    report = {"measured_at": datetime.now(timezone.utc).isoformat(), "database": "postgresql",
              "loads": loads, "query_plans": plans, "maintenance": maintenance,
              "evidence": "measured"}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str))
    print(args.output)


if __name__ == "__main__": main()
