from pathlib import Path


def test_console_exposes_read_only_dashboard_contract():
    console = Path("arm_bridge/console.py").read_text(encoding="utf-8")
    html = Path("arm_bridge/console_assets/index.html").read_text(encoding="utf-8")
    js = Path("arm_bridge/console_assets/app.js").read_text(encoding="utf-8")
    assert 'path == "/api/realsense/benchmark-dashboard"' in console
    assert '--benchmark-report' in console and '--gate-report' in console
    assert 'id="benchmarkHealth"' in html
    assert 'id="benchmarkRows"' in html
    assert 'id="benchmarkFailures"' in html
    assert "NO BASELINE WRITE · NO MOTION" in html
    assert "api('/api/realsense/benchmark-dashboard')" in js
