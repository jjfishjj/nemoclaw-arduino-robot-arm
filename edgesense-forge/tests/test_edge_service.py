from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError

from edge_service.benchmark import run_benchmark
from edge_service.inference import evaluate
from edge_service.inference_engines import InferenceManager
from edge_service.runtime import RuntimeRegistry
from edge_service.schemas import BenchmarkRequest, EdgeEvent, Telemetry, utc_now
from edge_service.storage import EventStore

MANAGER = InferenceManager()


def telemetry(**overrides):
    payload = {
        "schema_version": "1.0",
        "device_id": "motor-01",
        "ts": datetime.now(timezone.utc),
        "temperature_c": 42.0,
        "accel_rms_g": 0.18,
        "sample_rate_hz": 100,
    }
    payload.update(overrides)
    return Telemetry.model_validate(payload)


class SchemaTests(unittest.TestCase):
    def test_valid_telemetry(self):
        result = telemetry()
        self.assertEqual(result.device_id, "motor-01")

    def test_missing_device_id_is_rejected(self):
        with self.assertRaises(ValidationError):
            Telemetry.model_validate({
                "schema_version": "1.0",
                "ts": datetime.now(timezone.utc),
                "temperature_c": 42,
                "accel_rms_g": 0.1,
                "sample_rate_hz": 100,
            })

    def test_naive_timestamp_is_rejected(self):
        with self.assertRaises(ValidationError):
            telemetry(ts=datetime.now())


class InferenceTests(unittest.TestCase):
    def test_normal_signal(self):
        result = evaluate(telemetry(), manager=MANAGER)
        self.assertFalse(result.is_anomaly)
        self.assertEqual(result.reason_codes, ["WITHIN_RANGE"])
        self.assertEqual(result.engine, "onnxruntime")

    def test_overheat(self):
        result = evaluate(telemetry(temperature_c=78), manager=MANAGER)
        self.assertTrue(result.is_anomaly)
        self.assertIn("TEMP_HIGH", result.reason_codes)

    def test_vibration_anomaly(self):
        result = evaluate(telemetry(accel_rms_g=1.4), manager=MANAGER)
        self.assertTrue(result.is_anomaly)
        self.assertIn("VIBRATION_HIGH", result.reason_codes)

    def test_custom_threshold(self):
        result = evaluate(
            telemetry(temperature_c=60, accel_rms_g=0.5),
            manager=MANAGER,
            anomaly_threshold=0.5,
        )
        self.assertTrue(result.is_anomaly)
        self.assertEqual(result.reason_codes, ["SCORE_HIGH"])

    def test_tensorrt_is_honestly_unavailable_off_jetson(self):
        tensorrt = next(item for item in MANAGER.engines() if item["engine"] == "tensorrt")
        self.assertFalse(tensorrt["available"])
        self.assertIn("not detected as NVIDIA Jetson", tensorrt["reason"])


class BenchmarkTests(unittest.TestCase):
    def test_benchmark_reports_warmup_and_percentiles(self):
        result = run_benchmark(MANAGER, BenchmarkRequest(warmup_runs=2, measured_runs=20))
        self.assertEqual(result.engine, "onnxruntime")
        self.assertEqual(result.warmup_runs, 2)
        self.assertEqual(result.measured_runs, 20)
        self.assertLessEqual(result.p50_ms, result.p95_ms)
        self.assertEqual(result.evidence, "measured")


class RegistryTests(unittest.TestCase):
    def test_device_thresholds_are_isolated(self):
        registry = RuntimeRegistry()
        registry.configure("motor-01", anomaly_threshold=0.55, temperature_threshold_c=65)
        self.assertEqual(registry.get("motor-01").anomaly_threshold, 0.55)
        self.assertEqual(registry.get("unknown").anomaly_threshold, 0.7)


class StorageTests(unittest.TestCase):
    def test_event_and_anomaly_are_persisted(self):
        with TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "test.db")
            sample = telemetry(temperature_c=80)
            result = evaluate(sample, manager=MANAGER)
            store.save_event(EdgeEvent(
                received_at=utc_now(), topic="edgesense/v1/motor-01/telemetry",
                telemetry=sample, inference=result,
            ))
            self.assertEqual(store.summary()["samples"], 1)
            self.assertEqual(store.summary()["anomalies"], 1)
            self.assertEqual(store.history("motor-01")[0]["reason_codes"], ["TEMP_HIGH"])
            self.assertEqual(len(store.anomalies("motor-01")), 1)

    def test_alert_workflow_rules_and_cursor_page(self):
        with TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "test.db")
            for index in range(3):
                sample = telemetry(temperature_c=80 + index)
                store.save_event(EdgeEvent(received_at=utc_now(), topic="test",
                    telemetry=sample, inference=evaluate(sample, manager=MANAGER)))
            first = store.alert_page(limit=2)
            self.assertEqual(len(first["items"]), 2)
            self.assertIsNotNone(first["next_cursor"])
            second = store.alert_page(cursor=first["next_cursor"], limit=2)
            self.assertEqual(len(second["items"]), 1)
            alert_id = first["items"][0]["alert_id"]
            updated = store.update_alert(alert_id, "acknowledged", "bearing inspected", "tester", utc_now().isoformat())
            self.assertEqual(updated["status"], "acknowledged")
            self.assertEqual(updated["note"], "bearing inspected")
            rule = store.upsert_rule("motor-01", True, 0.8, 75, 45, utc_now().isoformat())
            self.assertEqual(rule["retention_days"], 45)
            self.assertEqual(store.get_rule("motor-01")["anomaly_threshold"], 0.8)

    def test_disabled_rule_suppresses_workflow_alert_not_telemetry(self):
        with TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "test.db")
            sample = telemetry(temperature_c=90)
            store.save_event(EdgeEvent(received_at=utc_now(), topic="test", telemetry=sample,
                inference=evaluate(sample, manager=MANAGER)), create_alert=False)
            self.assertEqual(store.summary()["samples"], 1)
            self.assertEqual(store.summary()["anomalies"], 1)
            self.assertEqual(store.alert_page()["items"], [])

    def test_benchmark_history_is_persisted(self):
        with TemporaryDirectory() as directory:
            store = EventStore(Path(directory) / "test.db")
            result = run_benchmark(MANAGER, BenchmarkRequest(warmup_runs=1, measured_runs=10))
            store.save_benchmark(result)
            history = store.benchmarks()
            self.assertEqual(len(history), 1)
            self.assertEqual(history[0]["engine"], "onnxruntime")


if __name__ == "__main__":
    unittest.main()
