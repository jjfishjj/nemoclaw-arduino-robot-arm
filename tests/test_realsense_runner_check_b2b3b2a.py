import importlib.metadata
import json
from pathlib import Path
from types import SimpleNamespace

from arm_bridge.realsense_runner_check import inspect_runner, main, markdown_report


def _version(_name):
    return "2.56.5"


def _disk(_path):
    return SimpleNamespace(free=12 * 1024 ** 3)


def test_fixture_runner_passes_without_physical_usb(tmp_path):
    bag = tmp_path / "capture.bag"
    bag.write_bytes(b"fixture")
    report = inspect_runner(
        bag,
        labels=["self-hosted", "Linux", "X64", "realsense"],
        which=lambda _name: "/usr/bin/rs-enumerate-devices",
        disk_usage=_disk,
        usb_root=tmp_path / "missing-usb",
        package_version=_version,
    )
    assert report["ok"] is True
    usb = next(check for check in report["checks"] if check["name"] == "usb_permissions")
    assert usb["ok"] is False and usb["required"] is False
    assert "WARN" in markdown_report(report)


def test_required_checks_fail_closed(tmp_path):
    bag = tmp_path / "capture.txt"

    def missing(_name):
        raise importlib.metadata.PackageNotFoundError

    report = inspect_runner(
        bag,
        labels=["self-hosted"],
        min_free_gib=5,
        which=lambda _name: None,
        disk_usage=lambda _path: SimpleNamespace(free=1024),
        usb_root=tmp_path / "usb",
        package_version=missing,
    )
    assert report["ok"] is False
    assert set(report["failures"]) == {
        "librealsense_python", "librealsense_cli", "runner_labels", "disk_space", "bag_readable"
    }
    assert report["motion_enabled"] is False


def test_cli_writes_rejected_report_on_failure(tmp_path):
    output = tmp_path / "report.json"
    code = main([
        "--bag", str(tmp_path / "missing.bag"),
        "--labels", "self-hosted,linux,x64,realsense",
        "--output", str(output),
    ])
    assert code == 2
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["ok"] is False
    assert "bag_readable" in report["failures"]
