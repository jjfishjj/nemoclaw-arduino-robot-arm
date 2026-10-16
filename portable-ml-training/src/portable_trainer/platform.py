from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class RuntimeInfo:
    platform: str
    workdir: str
    cuda_visible_devices: str | None
    world_size: int
    local_rank: int
    has_hf_token: bool
    has_hub_target: bool

    def to_dict(self) -> dict:
        return asdict(self)


def detect_platform() -> str:
    explicit = os.environ.get("ML_PLATFORM")
    if explicit:
        return explicit.lower()
    if os.environ.get("COLAB_RELEASE_TAG") or os.environ.get("COLAB_GPU"):
        return "colab"
    if os.environ.get("RUNPOD_POD_ID"):
        return "runpod"
    if os.environ.get("HF_JOB_ID") or os.environ.get("SPACE_ID"):
        return "huggingface"
    return "generic-linux"


def runtime_info() -> RuntimeInfo:
    return RuntimeInfo(
        platform=detect_platform(),
        workdir=os.environ.get("ML_WORKDIR", "outputs"),
        cuda_visible_devices=os.environ.get("CUDA_VISIBLE_DEVICES"),
        world_size=int(os.environ.get("WORLD_SIZE", "1")),
        local_rank=int(os.environ.get("LOCAL_RANK", "0")),
        has_hf_token=bool(os.environ.get("HF_TOKEN")),
        has_hub_target=bool(os.environ.get("HF_MODEL_ID")),
    )
