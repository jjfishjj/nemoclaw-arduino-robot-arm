#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PLATFORM="${ML_PLATFORM:-generic-linux}"
PERSISTENT_ROOT="${PERSISTENT_ROOT:-${PROJECT_DIR}/persistent}"
HF_CACHE_DIR="${HF_HOME:-${PERSISTENT_ROOT}/hf-cache}"
WORK_DIR="${ML_WORKDIR:-${PERSISTENT_ROOT}/checkpoints}"

mkdir -p "${HF_CACHE_DIR}" "${WORK_DIR}"
export HF_HOME="${HF_CACHE_DIR}"
export ML_WORKDIR="${WORK_DIR}"
export ML_PLATFORM="${PLATFORM}"

exec "${PROJECT_DIR}/scripts/run.sh" "$@"
