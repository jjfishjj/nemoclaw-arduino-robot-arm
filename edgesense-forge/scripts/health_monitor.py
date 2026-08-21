#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone


def main() -> None:
    parser = argparse.ArgumentParser(description="EdgeSense readiness probe for schedulers and monitors")
    parser.add_argument("--url", default="http://127.0.0.1:8000/health/ready")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args()
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        with urllib.request.urlopen(args.url, timeout=args.timeout) as response:
            payload = json.load(response)
            result = {"checked_at": checked_at, "url": args.url, "status": response.status, "payload": payload}
            print(json.dumps(result, default=str))
            if response.status != 200 or payload.get("status") != "ready":
                raise SystemExit(1)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        print(json.dumps({"checked_at": checked_at, "url": args.url, "status": "failed", "error": str(exc)}))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
