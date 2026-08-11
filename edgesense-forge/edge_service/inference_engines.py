from __future__ import annotations

import hashlib
import importlib.util
import json
import platform
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from time import perf_counter_ns

import numpy as np
import onnxruntime as ort

from .schemas import Telemetry

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_DIR = ROOT / "models" / "motor-anomaly-0.2"


class InferenceEngine(ABC):
    name: str

    @property
    @abstractmethod
    def available(self) -> bool: ...

    @abstractmethod
    def predict_score(self, telemetry: Telemetry) -> tuple[float, float]: ...

    @abstractmethod
    def metadata(self) -> dict: ...


class ONNXRuntimeEngine(InferenceEngine):
    name = "onnxruntime"

    def __init__(self, model_dir: Path = DEFAULT_MODEL_DIR) -> None:
        self.model_path = model_dir / "model.onnx"
        self.metadata_path = model_dir / "metadata.json"
        if not self.model_path.exists() or not self.metadata_path.exists():
            raise FileNotFoundError("ONNX model artifact is missing; run scripts/build_model.py")
        self._metadata = json.loads(self.metadata_path.read_text())
        digest = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
        if digest != self._metadata["sha256"]:
            raise RuntimeError("ONNX model checksum does not match metadata")
        self.session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

    @property
    def available(self) -> bool:
        return True

    def predict_score(self, telemetry: Telemetry) -> tuple[float, float]:
        features = np.array(
            [[telemetry.temperature_c, telemetry.accel_rms_g]],
            dtype=np.float32,
        )
        started = perf_counter_ns()
        output = self.session.run([self.output_name], {self.input_name: features})[0]
        latency_ms = (perf_counter_ns() - started) / 1_000_000
        return float(output[0][0]), latency_ms

    def metadata(self) -> dict:
        return {
            **self._metadata,
            "engine": self.name,
            "available": True,
            "runtime_version": ort.__version__,
            "providers": self.session.get_providers(),
            "device": ort.get_device(),
        }


class TensorRTEngine(InferenceEngine):
    name = "tensorrt"

    def __init__(self, model_dir: Path = DEFAULT_MODEL_DIR) -> None:
        self._module_present = importlib.util.find_spec("tensorrt") is not None
        self._jetson_present = Path("/etc/nv_tegra_release").exists()
        self.engine_path = model_dir / "model.plan"
        self._trtexec = shutil.which("trtexec")
        self._reason = self._availability_reason()

    @property
    def available(self) -> bool:
        return self._module_present and self._jetson_present and self.engine_path.exists()

    def predict_score(self, telemetry: Telemetry) -> tuple[float, float]:
        raise RuntimeError(self._reason)

    def metadata(self) -> dict:
        return {
            "engine": self.name,
            "available": self.available,
            "runtime_version": None,
            "providers": [],
            "device": platform.machine(),
            "reason": self._reason,
            "requires": ["NVIDIA Jetson", "TensorRT Python runtime", "built engine plan"],
            "engine_path": str(self.engine_path),
            "trtexec_available": self._trtexec is not None,
        }

    def _availability_reason(self) -> str:
        if not self._jetson_present:
            return "TensorRT unavailable: this host is not detected as NVIDIA Jetson."
        if not self._module_present:
            return "TensorRT unavailable: Python runtime is not installed."
        if not self.engine_path.exists():
            return "TensorRT runtime detected; run jetson/build_engine.sh to create model.plan."
        return "TensorRT engine is available."


class InferenceManager:
    def __init__(self) -> None:
        self.onnx = ONNXRuntimeEngine()
        self.tensorrt = TensorRTEngine()
        self.active = self.onnx

    def engines(self) -> list[dict]:
        return [self.onnx.metadata(), self.tensorrt.metadata()]

    def predict_score(self, telemetry: Telemetry) -> tuple[float, float, str, str]:
        score, latency_ms = self.active.predict_score(telemetry)
        metadata = self.active.metadata()
        return score, latency_ms, self.active.name, metadata["model_version"]
