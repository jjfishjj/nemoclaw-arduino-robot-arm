#!/usr/bin/env bash
set -euo pipefail

: "${TRAINING_IMAGE:?Set TRAINING_IMAGE to a pushed image, e.g. ghcr.io/user/portable-ml-training:latest}"
: "${HF_MODEL_ID:?Set HF_MODEL_ID to the destination model repository}"

HF_FLAVOR="${HF_FLAVOR:-a10g-large}"
JOB_NAME="${JOB_NAME:-portable-qlora}"
ML_CONFIG="${ML_CONFIG:-/workspace/configs/qlora-smoke.json}"

exec hf jobs run \
  --name "${JOB_NAME}" \
  --flavor "${HF_FLAVOR}" \
  --secrets HF_TOKEN \
  --env ML_PLATFORM=huggingface \
  --env ML_CONFIG="${ML_CONFIG}" \
  --env HF_MODEL_ID="${HF_MODEL_ID}" \
  "${TRAINING_IMAGE}" \
  /workspace/scripts/run.sh
