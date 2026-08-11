#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a recoverable EdgeSense database backup")
    parser.add_argument("--sqlite", type=Path, default=Path("data/edgesense.db"))
    parser.add_argument("--output-dir", type=Path, default=Path("backups"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        output = args.output_dir / f"edgesense-postgres-{stamp}.dump"
        subprocess.run(["pg_dump", "--format=custom", "--no-owner", "--file", str(output), database_url], check=True)
    else:
        output = args.output_dir / f"edgesense-sqlite-{stamp}.db"
        with sqlite3.connect(args.sqlite) as source, sqlite3.connect(output) as target:
            source.backup(target)
            if target.execute("pragma integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("backup integrity check failed")
    print(output)


if __name__ == "__main__": main()
