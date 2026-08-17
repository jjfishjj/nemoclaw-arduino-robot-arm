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
            ("mean_gazebo_update_fps", "minimum_mean_gazebo_update_fps", ">="),
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
            ("gazebo_update_fps", "minimum_mean_gazebo_update_fps", ">="),
            ("peak_gpu_memory_mib", "maximum_peak_gpu_memory_mib", "<="),
            ("mean_planning_latency_ms", "maximum_mean_planning_latency_ms", "<="),
            ("mcap_size_mib", "maximum_mcap_size_mib", "<="),
        ]
        timeout_rate = 1.0 if report.get("timed_out") else 0.0
    for metric, threshold_name, operator in checks:
        value = report.get(metric)
        if threshold_name not in thresholds:
            continue
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


def attach_runner_metrics(report, runner_metrics):
    merged = dict(report)
    if runner_metrics:
        merged["job_queue_seconds"] = runner_metrics.get("job_queue_seconds")
        merged["runner_image_id"] = runner_metrics.get("image_id")
    return merged


def main(args=None):
    parser = argparse.ArgumentParser(description="Fail CI when Rover benchmark safety regresses")
    parser.add_argument("report", help="Trial or summary JSON")
    parser.add_argument("thresholds", help="Versioned threshold JSON")
    parser.add_argument("--runner-metrics", help="Optional ephemeral runner telemetry JSON")
    options = parser.parse_args(args)
    report = json.loads(Path(options.report).read_text())
    if options.runner_metrics:
        report = attach_runner_metrics(
            report, json.loads(Path(options.runner_metrics).read_text())
        )
    thresholds = json.loads(Path(options.thresholds).read_text())
    violations = evaluate_gate(report, thresholds)
    if "maximum_job_queue_seconds" in thresholds:
        queue_seconds = report.get("job_queue_seconds")
        if queue_seconds is None:
            violations.append("job_queue_seconds: missing (required for gate)")
        elif float(queue_seconds) > float(thresholds["maximum_job_queue_seconds"]):
            violations.append(
                f"job_queue_seconds: {queue_seconds} > allowed "
                f"{thresholds['maximum_job_queue_seconds']}"
            )
    if violations:
        print("FAIL: benchmark gate rejected the report")
        for violation in violations:
            print(f"- {violation}")
            print(f"::error title=Rover benchmark regression::{violation}")
        raise SystemExit(1)
    print("PASS: benchmark meets all navigation and safety thresholds")


if __name__ == "__main__":
    main()
