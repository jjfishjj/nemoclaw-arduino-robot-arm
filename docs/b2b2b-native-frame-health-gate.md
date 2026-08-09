# B2-B2B — Native frame health gate

The live RGB-D status now classifies every filtered frame as `HEALTHY`,
`DEGRADED`, or `BLOCKED`. The gate observes the slower of raw/filtered FPS,
native filter latency, frame age, and filtered invalid-depth ratio.

| Signal | Healthy | Blocked |
| --- | ---: | ---: |
| FPS | ≥ 1.5 | < 0.5 |
| Filter latency | ≤ 20 ms | > 100 ms |
| Frame age | ≤ 750 ms | > 1000 ms |
| Invalid depth | ≤ 10% | > 50% |

Values between the healthy and blocked thresholds are `DEGRADED`. A stopped or
disconnected stream, or missing frame metrics, is always `BLOCKED`. The first
sample is `DEGRADED` while FPS warms up.

The API includes machine-readable reasons, observed values, and limits under
`status.frame_health`. This is an observability gate only: `motion_enabled`
remains false in every health state.
