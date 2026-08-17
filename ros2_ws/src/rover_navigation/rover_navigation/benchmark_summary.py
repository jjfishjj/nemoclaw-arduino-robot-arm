import argparse
import json
from pathlib import Path


def summarize(reports):
    if not reports:
        raise ValueError("at least one report is required")
    mean = lambda key: sum(float(report[key]) for report in reports) / len(reports)
    def optional_values(key):
        return [float(report[key]) for report in reports if report.get(key) is not None]

    def optional_mean(key):
        values = optional_values(key)
        return sum(values) / len(values) if values else None

    def optional_max(key):
        values = optional_values(key)
        return max(values) if values else None
    stop_distances = [report["minimum_stop_distance_m"] for report in reports
                      if report.get("minimum_stop_distance_m") is not None]
    total_goals = sum(report["goal_count"] for report in reports)
    total_contacts = sum(report.get("contact_collision_events", 0) for report in reports)
    timed_out = sum(bool(report.get("timed_out")) for report in reports)
    return {
        "schema_version": 2,
        "trial_count": len(reports),
        "successful_trials": sum(bool(report["navigation_success"]) for report in reports),
        "trial_success_rate": sum(bool(report["navigation_success"]) for report in reports) / len(reports),
        "mean_waypoint_success_rate": mean("success_rate"),
        "mean_elapsed_seconds": mean("elapsed_seconds"),
        "mean_path_length_m": mean("path_length_m"),
        "mean_minimum_stop_distance_m": (
            sum(stop_distances) / len(stop_distances) if stop_distances else None
        ),
        "total_contact_collision_events": total_contacts,
        "contact_collision_rate_per_goal": total_contacts / total_goals if total_goals else None,
        "timed_out_trials": timed_out,
        "timeout_rate": timed_out / len(reports),
        "mean_real_time_factor": optional_mean("real_time_factor"),
        "mean_planning_latency_ms": optional_mean("mean_planning_latency_ms"),
        "peak_gpu_memory_mib": optional_max("peak_gpu_memory_mib"),
        "peak_gpu_memory_utilization_ratio": optional_max("peak_gpu_memory_utilization_ratio"),
        "peak_gpu_temperature_c": optional_max("peak_gpu_temperature_c"),
        "mean_gpu_utilization_percent": optional_mean("mean_gpu_utilization_percent"),
        "minimum_disk_free_gib": (
            min(optional_values("minimum_disk_free_gib"))
            if optional_values("minimum_disk_free_gib") else None
        ),
        "maximum_mcap_size_mib": optional_max("mcap_size_mib"),
        "mean_mcap_size_mib": optional_mean("mcap_size_mib"),
    }


def main(args=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("reports", nargs="+")
    options = parser.parse_args(args)
    reports = [json.loads(Path(path).read_text()) for path in options.reports]
    summary = summarize(reports)
    Path(options.output).write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
