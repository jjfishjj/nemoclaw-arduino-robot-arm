from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from portable_trainer.config import ConfigError, load_config
from portable_trainer.platform import runtime_info


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--allow-cpu", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures: list[str] = []
    warnings: list[str] = []
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"FAIL config: {exc}")
        return 2

    nvidia_smi = shutil.which("nvidia-smi")
    gpu_name = None
    if nvidia_smi:
        result = subprocess.run(
            [nvidia_smi, "--query-gpu=name,memory.total", "--format=csv,noheader"],
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            gpu_name = result.stdout.strip()
        else:
            failures.append(f"nvidia-smi failed: {result.stderr.strip()}")
    elif not args.allow_cpu:
        failures.append("nvidia-smi not found; this training template requires an NVIDIA GPU")
    else:
        warnings.append("GPU check skipped because --allow-cpu was supplied")

    output_dir = Path(config["output"]["directory"])
    output_dir.mkdir(parents=True, exist_ok=True)
    free_gb = shutil.disk_usage(output_dir).free / (1024**3)
    if free_gb < 20:
        warnings.append(f"Only {free_gb:.1f} GiB free under {output_dir}")

    if config["output"].get("push_to_hub") and not os.environ.get("HF_TOKEN"):
        failures.append("HF_TOKEN is required because output.push_to_hub=true")

    payload = {
        "runtime": runtime_info().to_dict(),
        "gpu": gpu_name,
        "output_dir": str(output_dir.resolve()),
        "free_disk_gib": round(free_gb, 1),
        "warnings": warnings,
        "failures": failures,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failures:
        print("PREFLIGHT FAILED", file=sys.stderr)
        return 1
    print("PREFLIGHT OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
