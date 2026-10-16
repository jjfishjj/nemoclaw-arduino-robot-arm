from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from pathlib import Path
from typing import Any

from portable_trainer.checkpoints import resolve_resume_checkpoint
from portable_trainer.config import ConfigError, load_config, redacted_config
from portable_trainer.platform import runtime_info


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Portable QLoRA/LoRA/full fine-tuning")
    parser.add_argument("--config", required=True, help="Path to a JSON configuration")
    parser.add_argument("--dry-run", action="store_true", help="Validate without loading ML libraries")
    return parser.parse_args()


def maybe_download_hub_checkpoint(config: dict[str, Any], output_dir: Path) -> None:
    if not config["resume"].get("allow_hub_checkpoint", False):
        return
    if not config["output"].get("hub_model_id") or not os.environ.get("HF_TOKEN"):
        return
    if resolve_resume_checkpoint(config, output_dir):
        return

    from huggingface_hub import snapshot_download

    subdir = config["resume"].get("hub_checkpoint_subdir", "last-checkpoint")
    print(f"No local checkpoint; checking Hub subdirectory {subdir!r}")
    try:
        snapshot_download(
            repo_id=config["output"]["hub_model_id"],
            repo_type="model",
            allow_patterns=[f"{subdir}/**"],
            local_dir=output_dir,
            token=os.environ["HF_TOKEN"],
        )
    except Exception as exc:  # A new job may not have a repository yet.
        print(f"Hub checkpoint unavailable: {exc}")


def format_record(record: dict[str, Any], dataset_config: dict[str, Any]) -> str:
    text_field = dataset_config.get("text_field")
    if text_field:
        value = record.get(text_field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Dataset record has no non-empty {text_field!r} text")
        return value
    prompt = record.get(dataset_config["prompt_field"], "")
    response = record.get(dataset_config["response_field"], "")
    return f"### Instruction\n{prompt}\n\n### Response\n{response}"


def choose_precision(torch: Any, requested: Any) -> tuple[bool, bool]:
    cuda = torch.cuda.is_available()
    bf16_supported = cuda and getattr(torch.cuda, "is_bf16_supported", lambda: False)()
    if requested == "auto":
        return bf16_supported, cuda and not bf16_supported
    if bool(requested):
        return True, False
    return False, cuda


def build_training_arguments(config: dict[str, Any], torch: Any) -> Any:
    from transformers import TrainingArguments

    training = config["training"]
    output = config["output"]
    bf16, fp16 = choose_precision(torch, training.get("bf16", "auto"))
    kwargs = {
        "output_dir": output["directory"],
        "run_name": config.get("run_name"),
        "num_train_epochs": training.get("epochs", 1),
        "max_steps": training.get("max_steps", -1),
        "learning_rate": training.get("learning_rate", 2e-4),
        "per_device_train_batch_size": training["per_device_train_batch_size"],
        "per_device_eval_batch_size": training.get("per_device_eval_batch_size", 1),
        "gradient_accumulation_steps": training["gradient_accumulation_steps"],
        "gradient_checkpointing": training.get("gradient_checkpointing", True),
        "logging_steps": training.get("logging_steps", 10),
        "save_steps": training.get("save_steps", 100),
        "eval_steps": training.get("eval_steps", 100),
        "save_strategy": "steps",
        "eval_strategy": "steps",
        "save_total_limit": training.get("save_total_limit", 3),
        "warmup_ratio": training.get("warmup_ratio", 0.03),
        "weight_decay": training.get("weight_decay", 0.0),
        "seed": training.get("seed", 42),
        "bf16": bf16,
        "fp16": fp16,
        "tf32": bool(training.get("tf32", True) and torch.cuda.is_available()),
        "optim": training.get("optim", "paged_adamw_8bit"),
        "report_to": training.get("report_to", []),
        "remove_unused_columns": False,
        "ddp_find_unused_parameters": False,
        "push_to_hub": output.get("push_to_hub", False),
        "hub_model_id": output.get("hub_model_id"),
        "hub_private_repo": output.get("hub_private_repo", True),
        "hub_strategy": output.get("hub_strategy", "checkpoint"),
    }
    signature = inspect.signature(TrainingArguments.__init__)
    if "enable_jit_checkpoint" in signature.parameters:
        kwargs["enable_jit_checkpoint"] = True
    return TrainingArguments(**kwargs)


def run_training(config: dict[str, Any]) -> None:
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForLanguageModeling,
        Trainer,
    )

    output_dir = Path(config["output"]["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)
    maybe_download_hub_checkpoint(config, output_dir)
    resume_path = resolve_resume_checkpoint(config, output_dir)

    model_cfg = config["model"]
    method_cfg = config["method"]
    tokenizer = AutoTokenizer.from_pretrained(
        model_cfg["name_or_path"], trust_remote_code=model_cfg.get("trust_remote_code", False)
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    quantization_config = None
    model_kwargs: dict[str, Any] = {
        "trust_remote_code": model_cfg.get("trust_remote_code", False),
    }
    if method_cfg["type"] == "qlora":
        compute_dtype = torch.bfloat16 if choose_precision(torch, "auto")[0] else torch.float16
        quantization_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=compute_dtype,
        )
        model_kwargs["quantization_config"] = quantization_config
        local_rank = int(os.environ.get("LOCAL_RANK", "0"))
        model_kwargs["device_map"] = {"": local_rank}
    model = AutoModelForCausalLM.from_pretrained(model_cfg["name_or_path"], **model_kwargs)
    model.config.use_cache = False

    if method_cfg["type"] in {"qlora", "lora"}:
        if method_cfg["type"] == "qlora":
            model = prepare_model_for_kbit_training(
                model, use_gradient_checkpointing=config["training"].get("gradient_checkpointing", True)
            )
        lora_config = LoraConfig(
            r=method_cfg.get("lora_r", 16),
            lora_alpha=method_cfg.get("lora_alpha", 32),
            lora_dropout=method_cfg.get("lora_dropout", 0.05),
            target_modules=method_cfg.get("target_modules", "all-linear"),
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)
        model.print_trainable_parameters()

    data_cfg = config["dataset"]
    load_kwargs = {}
    if data_cfg.get("subset"):
        load_kwargs["name"] = data_cfg["subset"]
    raw = load_dataset(data_cfg["name"], **load_kwargs)
    train_dataset = raw[data_cfg["train_split"]]
    eval_split = data_cfg.get("eval_split")
    if eval_split:
        eval_dataset = raw[eval_split]
    else:
        split = train_dataset.train_test_split(
            test_size=data_cfg.get("validation_ratio", 0.02), seed=config["training"].get("seed", 42)
        )
        train_dataset, eval_dataset = split["train"], split["test"]

    if data_cfg.get("max_train_samples"):
        train_dataset = train_dataset.select(range(min(len(train_dataset), data_cfg["max_train_samples"])))
    if data_cfg.get("max_eval_samples"):
        eval_dataset = eval_dataset.select(range(min(len(eval_dataset), data_cfg["max_eval_samples"])))

    def tokenize(batch: dict[str, list[Any]]) -> dict[str, Any]:
        size = len(next(iter(batch.values())))
        texts = [format_record({key: value[i] for key, value in batch.items()}, data_cfg) for i in range(size)]
        encoded = tokenizer(
            texts,
            truncation=True,
            max_length=model_cfg["max_seq_length"],
            padding=False,
        )
        return encoded

    train_dataset = train_dataset.map(tokenize, batched=True, remove_columns=train_dataset.column_names)
    eval_dataset = eval_dataset.map(tokenize, batched=True, remove_columns=eval_dataset.column_names)
    arguments = build_training_arguments(config, torch)
    trainer = Trainer(
        model=model,
        args=arguments,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        processing_class=tokenizer,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    print(f"Resume checkpoint: {resume_path or 'none'}")
    trainer.train(resume_from_checkpoint=str(resume_path) if resume_path else None)
    trainer.save_model(output_dir / "final-adapter")
    tokenizer.save_pretrained(output_dir / "final-adapter")
    if config["output"].get("push_to_hub"):
        trainer.push_to_hub(commit_message="Training complete")

    manifest = {
        "runtime": runtime_info().to_dict(),
        "config": redacted_config(config),
        "resume_checkpoint": str(resume_path) if resume_path else None,
    }
    (output_dir / "run-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    args = parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    plan = {
        "runtime": runtime_info().to_dict(),
        "config": redacted_config(config),
        "output_dir": config["output"]["directory"],
        "local_resume_checkpoint": str(
            resolve_resume_checkpoint(config, config["output"]["directory"])
            or "none"
        ),
    }
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("DRY RUN OK: configuration, environment overrides, and checkpoint scan passed")
        return 0
    run_training(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
