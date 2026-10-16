#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_PATH="${ML_CONFIG:-${PROJECT_DIR}/configs/qlora-smoke.json}"
NUM_GPUS="${NUM_GPUS:-1}"
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python3}"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="${PYTHON_BIN:-python}"
else
  echo "Neither python3 nor python was found" >&2
  exit 127
fi

cd "${PROJECT_DIR}"

if [[ "${1:-}" == "--dry-run" ]]; then
  exec "${PYTHON_BIN}" src/train.py --config "${CONFIG_PATH}" --dry-run
fi

"${PYTHON_BIN}" scripts/preflight.py --config "${CONFIG_PATH}"

if (( NUM_GPUS > 1 )); then
  exec torchrun --standalone --nproc_per_node="${NUM_GPUS}" \
    src/train.py --config "${CONFIG_PATH}"
fi

exec "${PYTHON_BIN}" src/train.py --config "${CONFIG_PATH}"
