#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${JETSON_HOST:-}" ]]; then
  echo "ERROR: set JETSON_HOST to an SSH host alias or user@host." >&2
  exit 2
fi
remote_dir="${JETSON_PROJECT_DIR:-~/edgesense-forge}"
project_dir="$(cd "$(dirname "$0")/.." && pwd)"

ssh -o BatchMode=yes "${JETSON_HOST}" "mkdir -p ${remote_dir}"
rsync -az --delete \
  --exclude .venv --exclude .platformio --exclude data --exclude backups --exclude '*.plan' \
  "${project_dir}/" "${JETSON_HOST}:${remote_dir}/"
ssh -t "${JETSON_HOST}" "cd ${remote_dir} && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && ./jetson/validate_on_jetson.sh ${JETSON_POWER_MODE:-}"
mkdir -p "${project_dir}/benchmarks/jetson"
rsync -az "${JETSON_HOST}:${remote_dir}/data/jetson-validation-*/" "${project_dir}/benchmarks/jetson/"
echo "Jetson evidence downloaded to benchmarks/jetson/"
