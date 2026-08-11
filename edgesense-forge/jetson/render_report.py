#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

directory = Path(sys.argv[1])
comparison = json.loads((directory / "comparison.json").read_text())
tegrastats = (directory / "tegrastats.log").read_text(errors="replace")
temps = [float(value) for value in re.findall(r"(?:CPU|GPU|SOC)@(\d+(?:\.\d+)?)C", tegrastats)]
onnx = comparison["onnxruntime"]; trt = comparison["tensorrt"]
report = f"""# EdgeSense Forge — Jetson validation report

Evidence status: **MEASURED ON TARGET**

| Engine | Runtime | P50 ms | P95 ms | Mean ms |
|---|---:|---:|---:|---:|
| ONNX Runtime | {onnx['runtime_version']} | {onnx['p50_ms']} | {onnx['p95_ms']} | {onnx['mean_ms']} |
| TensorRT FP16 | {trt['runtime_version']} | {trt['p50_ms']} | {trt['p95_ms']} | {trt['mean_ms']} |

- P95 speedup: **{comparison['p95_speedup']}×**
- Samples per engine: {trt['measured_runs']}
- Maximum observed reported temperature: {max(temps) if temps else 'not parsed'} °C
- Power-mode evidence: `power-mode.txt`
- Thermal/resource evidence: `tegrastats.log`
- Engine build evidence: `engine-build.log`

The TensorRT plan is target-specific and is intentionally not included in source control.
"""
(directory / "REPORT.md").write_text(report)
print(directory / "REPORT.md")
