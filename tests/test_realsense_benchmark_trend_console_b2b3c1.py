from pathlib import Path


def test_workflow_artifact_and_console_trend_contract():
    action = Path(".github/actions/realsense-native-gate/action.yml").read_text()
    html = Path("arm_bridge/console_assets/index.html").read_text()
    js = Path("arm_bridge/console_assets/app.js").read_text()
    console = Path("arm_bridge/console.py").read_text()
    assert "arm_bridge.realsense_benchmark_history" in action
    assert 'history-entry.json' in action
    assert action.index("realsense_benchmark_history") < action.index("uses: actions/upload-artifact@v4")
    assert '--benchmark-history-dir' in console
    assert 'id="trendCharts"' in html and 'id="trendCount"' in html
    assert "['latency_p50_ms', 'Latency P50', 'ms']" in js
    assert "['latency_p95_ms', 'Latency P95', 'ms']" in js
    assert "['fps', 'Throughput', 'FPS']" in js
    assert "entry.regression" in js
