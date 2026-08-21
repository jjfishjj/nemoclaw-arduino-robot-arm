#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from edge_service.benchmark import _percentile, run_benchmark
from edge_service.inference_engines import InferenceManager
from edge_service.schemas import BenchmarkRequest, BenchmarkResult
from edge_service.storage import EventStore

def tensor_rt_benchmark(warmup_runs: int, measured_runs: int) -> BenchmarkResult:
    try:
        import tensorrt as trt
    except ImportError as exc:
        raise SystemExit("TensorRT Python runtime is missing; run this comparison on Jetson") from exc
    engine = ROOT / "models" / "motor-anomaly-0.2" / "model.plan"
    if not engine.exists():
        raise SystemExit("model.plan is missing; run jetson/build_engine.sh first")
    with tempfile.TemporaryDirectory() as directory:
        times_path = Path(directory) / "times.json"
        subprocess.run(
            [
                "trtexec", f"--loadEngine={engine}", "--shapes=features:1x2",
                f"--warmUp={max(warmup_runs, 1) * 10}", f"--iterations={measured_runs}",
                "--useSpinWait", f"--exportTimes={times_path}",
            ],
            check=True,
        )
        samples = json.loads(times_path.read_text())
    latencies = [float(sample["computeMs"]) for sample in samples if "computeMs" in sample]
    if not latencies:
        raise RuntimeError("trtexec export did not contain computeMs samples")
    ordered = sorted(latencies)
    metadata = json.loads((ROOT / "models" / "motor-anomaly-0.2" / "metadata.json").read_text())
    return BenchmarkResult(
        engine="tensorrt", model_version=metadata["model_version"],
        runtime_version=trt.__version__, device="NVIDIA Jetson", host_arch=platform.machine(),
        warmup_runs=warmup_runs, measured_runs=len(latencies),
        mean_ms=round(statistics.fmean(latencies), 4),
        p50_ms=round(_percentile(ordered, 0.50), 4),
        p95_ms=round(_percentile(ordered, 0.95), 4), min_ms=round(ordered[0], 4),
        max_ms=round(ordered[-1], 4), measured_at=datetime.now(timezone.utc), evidence="measured",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare ONNX Runtime and TensorRT on Jetson")
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--database", type=Path, default=ROOT / "data" / "edgesense.db")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "engine-comparison.json")
    args = parser.parse_args()
    request = BenchmarkRequest(warmup_runs=args.warmup, measured_runs=args.iterations)
    onnx_result = run_benchmark(InferenceManager(), request)
    tensorrt_result = tensor_rt_benchmark(args.warmup, args.iterations)
    store = EventStore(args.database)
    store.save_benchmark(onnx_result)
    store.save_benchmark(tensorrt_result)
    output = {
        "onnxruntime": onnx_result.model_dump(mode="json"),
        "tensorrt": tensorrt_result.model_dump(mode="json"),
        "p95_speedup": round(onnx_result.p95_ms / tensorrt_result.p95_ms, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
