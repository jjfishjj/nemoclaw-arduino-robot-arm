import argparse
import json
from pathlib import Path


def evaluate_gate(report, thresholds):
    violations = []
    is_summary = "trial_count" in report
    if is_summary:
        checks = [
            ("trial_success_rate", "minimum_trial_success_rate", ">="),
            ("mean_waypoint_success_rate", "minimum_waypoint_success_rate", ">="),
            ("contact_collision_rate_per_goal", "maximum_contact_collision_rate_per_goal", "<="),
            ("mean_minimum_stop_distance_m", "minimum_mean_stop_distance_m", ">="),
            ("mean_real_time_factor", "minimum_mean_real_time_factor", ">="),
            ("peak_gpu_memory_mib", "maximum_peak_gpu_memory_mib", "<="),
            ("mean_planning_latency_ms", "maximum_mean_planning_latency_ms", "<="),
            ("maximum_mcap_size_mib", "maximum_mcap_size_mib", "<="),
        ]
        timeout_rate = report.get("timeout_rate", 0.0)
    else:
        checks = [
            ("success_rate", "minimum_waypoint_success_rate", ">="),
            ("contact_collision_rate", "maximum_contact_collision_rate_per_goal", "<="),
            ("minimum_stop_distance_m", "minimum_mean_stop_distance_m", ">="),
            ("real_time_factor", "minimum_mean_real_time_factor", ">="),
            ("peak_gpu_memory_mib", "maximum_peak_gpu_memory_mib", "<="),
            ("mean_planning_latency_ms", "maximum_mean_planning_latency_ms", "<="),
            ("mcap_size_mib", "maximum_mcap_size_mib", "<="),
        ]
        timeout_rate = 1.0 if report.get("timed_out") else 0.0
    for metric, threshold_name, operator in checks:
        value = report.get(metric)
        limit = thresholds[threshold_name]
        if value is None:
            violations.append(f"{metric}: missing (required for gate)")
        elif operator == ">=" and float(value) < float(limit):
            violations.append(f"{metric}: {value} < required {limit}")
        elif operator == "<=" and float(value) > float(limit):
            violations.append(f"{metric}: {value} > allowed {limit}")
    max_timeout = thresholds["maximum_timeout_rate"]
    if timeout_rate > max_timeout:
        violations.append(f"timeout_rate: {timeout_rate} > allowed {max_timeout}")
    return violations


def main(args=None):
    parser = argparse.ArgumentParser(description="Fail CI when Rover benchmark safety regresses")
    parser.add_argument("report", help="Trial or summary JSON")
    parser.add_argument("thresholds", help="Versioned threshold JSON")
    options = parser.parse_args(args)
    report = json.loads(Path(options.report).read_text())
    thresholds = json.loads(Path(options.thresholds).read_text())
    violations = evaluate_gate(report, thresholds)
    if violations:
        print("FAIL: benchmark gate rejected the report")
        for violation in violations:
            print(f"- {violation}")
        raise SystemExit(1)
    print("PASS: benchmark meets all navigation and safety thresholds")


if __name__ == "__main__":
    main()
