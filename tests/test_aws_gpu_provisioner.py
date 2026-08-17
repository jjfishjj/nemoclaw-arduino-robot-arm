import hashlib
import hmac
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


class _Boto3(types.ModuleType):
    def client(self, _name):
        raise AssertionError("unexpected AWS call")


sys.modules.setdefault("boto3", _Boto3("boto3"))
PATH = Path(__file__).parents[1] / "ops/ros_gpu_runner/aws_provisioner/handler.py"
SPEC = importlib.util.spec_from_file_location("aws_runner_handler", PATH)
HANDLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HANDLER)


class AwsProvisionerTest(unittest.TestCase):
    def test_signature_validation(self):
        body = b'{"action":"queued"}'
        signature = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        self.assertTrue(HANDLER._authorized({"X-Hub-Signature-256": signature}, body, "secret"))
        self.assertFalse(HANDLER._authorized({"X-Hub-Signature-256": "bad"}, body, "secret"))

    def test_user_data_fetches_one_use_secret_to_tmpfs(self):
        data = HANDLER._user_data("arn:aws:secretsmanager:region:account:secret:job")
        self.assertIn("/run/secrets/ephemeral-runner.env", data)
        self.assertIn("delete-secret", data)
        self.assertIn("systemctl start ephemeral-gpu-runner.service", data)
        self.assertNotIn("short-token", data)

    def test_required_labels_include_ephemeral_gpu_contract(self):
        self.assertTrue({"gpu", "gazebo", "ephemeral"}.issubset(HANDLER.REQUIRED_LABELS))


if __name__ == "__main__":
    unittest.main()
