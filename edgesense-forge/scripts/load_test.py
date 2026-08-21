#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from edge_service.inference import evaluate
from edge_service.inference_engines import InferenceManager
from edge_service.schemas import EdgeEvent, Telemetry, utc_now
from edge_service.store_factory import create_store


def main() -> None:
    parser = argparse.ArgumentParser(description="Telemetry storage throughput test")
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--database", type=Path, default=Path("/tmp/edgesense-load-test.db"))
    args = parser.parse_args()
    store = create_store(os.getenv("DATABASE_URL"), args.database)
    manager = InferenceManager()

    def write(index: int) -> float:
        telemetry = Telemetry(schema_version="1.0", device_id=f"load-{index % 10:02d}",
            ts=datetime.now(timezone.utc), temperature_c=45 + index % 35,
            accel_rms_g=0.2 + (index % 20) / 20, sample_rate_hz=100)
        event = EdgeEvent(received_at=utc_now(), topic=f"edgesense/v1/{telemetry.device_id}/telemetry",
                          telemetry=telemetry, inference=evaluate(telemetry, manager=manager))
        started = perf_counter(); store.save_event(event); return (perf_counter() - started) * 1000

    started = perf_counter()
    with ThreadPoolExecutor(max_workers=args.workers) as pool: latencies = list(pool.map(write, range(args.events)))
    elapsed = perf_counter() - started; ordered = sorted(latencies)
    print(f"events={args.events} workers={args.workers} elapsed_s={elapsed:.3f} throughput_eps={args.events/elapsed:.1f}")
    print(f"write_mean_ms={statistics.fmean(latencies):.3f} write_p95_ms={ordered[int(len(ordered)*.95)-1]:.3f}")


if __name__ == "__main__": main()
