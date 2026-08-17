import argparse
import html
import json
from pathlib import Path

from .benchmark_summary import summarize


REQUIRED_FIELDS = {
    "goal_count", "completed_goals", "navigation_success", "success_rate",
    "elapsed_seconds", "path_length_m", "contact_collision_events",
}


def load_reports(paths):
    reports = []
    for path in paths:
        report = json.loads(Path(path).read_text())
        missing = REQUIRED_FIELDS - report.keys()
        if missing:
            raise ValueError(f"{path} missing fields: {', '.join(sorted(missing))}")
        report["trial_name"] = Path(path).stem
        reports.append(report)
    if not reports:
        raise ValueError("at least one trial report is required")
    return reports


def render_dashboard(reports, title="Rover Forge Benchmark"):
    summary = summarize(reports)
    payload = json.dumps({"reports": reports, "summary": summary}, separators=(",", ":")).replace(
        "<", "\\u003c"
    )
    safe_title = html.escape(title)
    template = Path(__file__).with_name("dashboard_template.html").read_text()
    return template.replace("__DASHBOARD_TITLE__", safe_title).replace("__DASHBOARD_DATA__", payload)


def main(args=None):
    parser = argparse.ArgumentParser(description="Generate a standalone Rover benchmark dashboard")
    parser.add_argument("output", help="Output HTML file")
    parser.add_argument("reports", nargs="+", help="Trial KPI JSON files")
    parser.add_argument("--title", default="Rover Forge Benchmark")
    options = parser.parse_args(args)
    reports = load_reports(options.reports)
    output = Path(options.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_dashboard(reports, options.title))
    print(f"Generated standalone dashboard with {len(reports)} trials: {output}")


if __name__ == "__main__":
    main()
