#!/usr/bin/env bash
set -euo pipefail

: "${TRAINING_IMAGE:?Set TRAINING_IMAGE to the built training image}"

PLATFORM="${ML_PLATFORM:-runpod}"
PERSISTENT_ROOT="${PERSISTENT_ROOT:-/workspace-data}"
HF_MODEL_ID="${HF_MODEL_ID:-}"

mkdir -p "${PERSISTENT_ROOT}/hf-cache" "${PERSISTENT_ROOT}/checkpoints"

docker_args=(
  run --rm --gpus all
  --shm-size=16g
  -e "ML_PLATFORM=${PLATFORM}"
  -e "ML_WORKDIR=/data/checkpoints"
  -e "HF_HOME=/data/hf-cache"
  -e "NUM_GPUS=${NUM_GPUS:-1}"
  -v "${PERSISTENT_ROOT}:/data"
)

if [[ -n "${HF_TOKEN:-}" ]]; then
  docker_args+=( -e HF_TOKEN )
fi
if [[ -n "${HF_MODEL_ID}" ]]; then
  docker_args+=( -e "HF_MODEL_ID=${HF_MODEL_ID}" )
fi

exec docker "${docker_args[@]}" "${TRAINING_IMAGE}" /workspace/scripts/run.sh
