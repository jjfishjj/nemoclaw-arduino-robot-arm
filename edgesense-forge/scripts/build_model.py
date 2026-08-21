"""Build the deterministic EdgeSense ONNX anomaly model artifact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "models" / "motor-anomaly-0.2"
MODEL_PATH = MODEL_DIR / "model.onnx"
METADATA_PATH = MODEL_DIR / "metadata.json"


def build() -> tuple[Path, Path]:
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    input_info = helper.make_tensor_value_info("features", TensorProto.FLOAT, [None, 2])
    output_info = helper.make_tensor_value_info("anomaly_score", TensorProto.FLOAT, [None, 1])

    mean = numpy_helper.from_array(np.array([50.0, 0.4], dtype=np.float32), name="feature_mean")
    scale = numpy_helper.from_array(np.array([15.0, 0.5], dtype=np.float32), name="feature_scale")
    weights = numpy_helper.from_array(np.array([[1.2], [2.5]], dtype=np.float32), name="weights")
    bias = numpy_helper.from_array(np.array([-1.2], dtype=np.float32), name="bias")

    nodes = [
        helper.make_node("Sub", ["features", "feature_mean"], ["centered"]),
        helper.make_node("Div", ["centered", "feature_scale"], ["normalized"]),
        helper.make_node("MatMul", ["normalized", "weights"], ["weighted"]),
        helper.make_node("Add", ["weighted", "bias"], ["logit"]),
        helper.make_node("Sigmoid", ["logit"], ["anomaly_score"]),
    ]

    graph = helper.make_graph(
        nodes,
        "edgesense-motor-anomaly",
        [input_info],
        [output_info],
        initializer=[mean, scale, weights, bias],
    )
    model = helper.make_model(
        graph,
        producer_name="edgesense-forge",
        producer_version="0.2.0",
        opset_imports=[helper.make_opsetid("", 17)],
    )
    model.ir_version = 10
    onnx.checker.check_model(model)
    onnx.save(model, MODEL_PATH)

    digest = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    metadata = {
        "model_id": "motor-anomaly-0.2",
        "model_version": "0.2.0",
        "format": "ONNX",
        "opset": 17,
        "input_name": "features",
        "input_shape": ["batch", 2],
        "features": [
            {"name": "temperature_c", "unit": "°C", "mean": 50.0, "scale": 15.0},
            {"name": "accel_rms_g", "unit": "g", "mean": 0.4, "scale": 0.5},
        ],
        "output_name": "anomaly_score",
        "default_threshold": 0.7,
        "purpose": "Deterministic prototype scorer; not a certified predictive-maintenance model.",
        "sha256": digest,
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n")
    return MODEL_PATH, METADATA_PATH


if __name__ == "__main__":
    model_path, metadata_path = build()
    print(model_path)
    print(metadata_path)
