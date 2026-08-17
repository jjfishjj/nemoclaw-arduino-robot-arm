import argparse
import csv
import json
import math
from pathlib import Path


def _number(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def directory_size_bytes(path):
    root = Path(path)
    if not root.exists():
        return 0
    if root.is_file():
        return root.stat().st_size
    return sum(item.stat().st_size for item in root.rglob("*") if item.is_file())


def summarize_gpu_csv(path):
    with Path(path).open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ValueError("GPU metrics CSV has no samples")

    def values(name):
        return [number for row in rows if (number := _number(row.get(name))) is not None]

    gpu_util = values("gpu_utilization_percent")
    memory_used = values("memory_used_mib")
    memory_total = values("memory_total_mib")
    temperatures = values("temperature_c")
    disk_free = values("disk_free_gib")
    if not gpu_util or not memory_used or not memory_total or not temperatures or not disk_free:
        raise ValueError("GPU metrics CSV is missing required numeric samples")
    utilization_ratios = [
        used / total for used, total in zip(memory_used, memory_total) if total > 0.0
    ]
    return {
        "gpu_sample_count": len(rows),
        "mean_gpu_utilization_percent": round(sum(gpu_util) / len(gpu_util), 3),
        "peak_gpu_utilization_percent": round(max(gpu_util), 3),
        "peak_gpu_memory_mib": round(max(memory_used), 3),
        "peak_gpu_memory_utilization_ratio": round(max(utilization_ratios), 6),
        "peak_gpu_temperature_c": round(max(temperatures), 3),
        "minimum_disk_free_gib": round(min(disk_free), 3),
    }


def enrich_report(report, gpu_metrics, mcap_size_bytes):
    enriched = dict(report)
    enriched.update(gpu_metrics)
    enriched["mcap_size_bytes"] = int(mcap_size_bytes)
    enriched["mcap_size_mib"] = round(mcap_size_bytes / (1024 * 1024), 3)
    enriched["schema_version"] = max(3, int(enriched.get("schema_version", 1)))
    return enriched


def main(args=None):
    parser = argparse.ArgumentParser(description="Attach GPU and MCAP metrics to a trial report")
    parser.add_argument("report")
    parser.add_argument("gpu_csv")
    parser.add_argument("mcap_path")
    options = parser.parse_args(args)
    report_path = Path(options.report)
    report = json.loads(report_path.read_text())
    enriched = enrich_report(
        report,
        summarize_gpu_csv(options.gpu_csv),
        directory_size_bytes(options.mcap_path),
    )
    report_path.write_text(json.dumps(enriched, indent=2, sort_keys=True) + "\n")
    print(json.dumps(enriched, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
