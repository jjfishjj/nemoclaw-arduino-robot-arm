from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when a training configuration is incomplete or inconsistent."""


def load_config(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    try:
        config = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid JSON in {source}: {exc}") from exc

    config = deepcopy(config)
    _apply_environment_overrides(config)
    validate_config(config)
    return config


def _apply_environment_overrides(config: dict[str, Any]) -> None:
    workdir = os.environ.get("ML_WORKDIR")
    if workdir:
        original = Path(config["output"]["directory"])
        config["output"]["directory"] = str(Path(workdir) / original.name)

    hub_model_id = os.environ.get("HF_MODEL_ID")
    if hub_model_id:
        config["output"]["hub_model_id"] = hub_model_id
        config["output"]["push_to_hub"] = True

    max_steps = os.environ.get("ML_MAX_STEPS")
    if max_steps:
        try:
            config["training"]["max_steps"] = int(max_steps)
        except ValueError as exc:
            raise ConfigError("ML_MAX_STEPS must be an integer") from exc


def validate_config(config: dict[str, Any]) -> None:
    for section in ("model", "dataset", "method", "training", "output", "resume"):
        if not isinstance(config.get(section), dict):
            raise ConfigError(f"Missing object section: {section}")

    required = {
        "model": ("name_or_path", "max_seq_length"),
        "dataset": ("name", "train_split"),
        "method": ("type",),
        "training": ("per_device_train_batch_size", "gradient_accumulation_steps"),
        "output": ("directory", "push_to_hub"),
        "resume": ("mode",),
    }
    for section, keys in required.items():
        for key in keys:
            if config[section].get(key) in (None, ""):
                raise ConfigError(f"Missing required setting: {section}.{key}")

    method = config["method"]["type"]
    if method not in {"qlora", "lora", "full"}:
        raise ConfigError("method.type must be one of: qlora, lora, full")
    if method == "qlora" and not config["method"].get("load_in_4bit", False):
        raise ConfigError("QLoRA requires method.load_in_4bit=true")

    dataset = config["dataset"]
    has_text = bool(dataset.get("text_field"))
    has_pair = bool(dataset.get("prompt_field") and dataset.get("response_field"))
    if not (has_text or has_pair):
        raise ConfigError(
            "Set dataset.text_field or both dataset.prompt_field and dataset.response_field"
        )

    output = config["output"]
    if output.get("push_to_hub") and not output.get("hub_model_id"):
        raise ConfigError("output.hub_model_id is required when push_to_hub=true")

    resume_mode = config["resume"]["mode"]
    if resume_mode not in {"auto", "never"} and not str(resume_mode).startswith("path:"):
        raise ConfigError("resume.mode must be auto, never, or path:/absolute/checkpoint")

    for path, value in (
        ("model.max_seq_length", config["model"]["max_seq_length"]),
        ("training.per_device_train_batch_size", config["training"]["per_device_train_batch_size"]),
        ("training.gradient_accumulation_steps", config["training"]["gradient_accumulation_steps"]),
    ):
        if not isinstance(value, int) or value <= 0:
            raise ConfigError(f"{path} must be a positive integer")


def redacted_config(config: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(config)
    for section in result.values():
        if not isinstance(section, dict):
            continue
        for key in list(section):
            if "token" in key.lower() or "secret" in key.lower():
                section[key] = "***"
    return result
