#!/usr/bin/env bash
set -euo pipefail

directory="${1:-$PWD/reports/random_benchmark}"
port="${2:-8080}"
if [[ ! -f "$directory/dashboard.html" ]]; then
  echo "Missing $directory/dashboard.html; run the benchmark first" >&2
  exit 2
fi
echo "Dashboard: http://127.0.0.1:$port/dashboard.html"
python3 -m http.server "$port" --directory "$directory"
