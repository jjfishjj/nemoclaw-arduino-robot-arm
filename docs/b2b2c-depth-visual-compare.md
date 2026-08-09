# B2-B2C — Raw / filtered depth visual comparison

The paired localhost console can render the latest raw or filtered depth frame
as a heatmap. Both views use one shared per-frame depth range so switching
before/after does not silently rescale the colors.

- Blue represents nearer valid depth and red represents farther valid depth.
- Invalid depth is black by default and magenta when **Invalid mask** is on.
- The mock fixture includes deterministic raw holes; the reviewed filter graph
  fills them, making the before/after behavior observable in CI.
- PNGs are generated server-side and returned with `no-store`; no depth data is
  written to browser storage or exposed without the HttpOnly paired session.

Endpoints fail closed before the first live frame and reject unknown views.
Depth visualization is read-only and never changes `motion_enabled: false`.
