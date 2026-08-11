# Performance evidence

| Target | Engine | Precision | P50 | P95 | Evidence |
|---|---|---|---:|---:|---|
| Apple arm64 development host | ONNX Runtime | FP32 | environment-dependent | environment-dependent | locally measurable |
| Jetson Orin/Nano | ONNX Runtime | FP32 | pending hardware | pending hardware | not yet measured |
| Jetson Orin/Nano | TensorRT | FP16 | pending hardware | pending hardware | not yet measured |

Run `jetson/validate_on_jetson.sh` to replace pending rows with target evidence.
Report JetPack/TensorRT versions, power mode, warm-up, sample count and temperature.

Storage load tests are workload-specific. Record backend, event count, worker count,
throughput and write P95; do not compare SQLite and PostgreSQL without equivalent disks.
`scripts/postgres_benchmark.py` refuses to run without `DATABASE_URL`, executes 10K and
100K loads, then records actual `EXPLAIN ANALYZE` plans for device history, active alerts,
and anomaly history. Generated reports are evidence artifacts, not source fixtures.
