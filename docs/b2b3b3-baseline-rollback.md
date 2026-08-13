# B2-B3B3 — Baseline rollback and revocation ledger

Every approved native baseline is stored permanently at
`benchmarks/realsense-baselines/<sha256>.json`. The JSONL ledger records each
`PROMOTE` or `ROLLBACK` action, baseline digest, actor, workflow run, reason,
timestamp, and the previous entry digest. Each entry hashes its canonical
contents, so mutation, deletion from the middle, reordering, and insertion are
detected before another governance action can proceed.

To roll back, run **RealSense Baseline Rollback** from the trusted default
branch, supply a previously promoted SHA-256 and a required reason, then approve
the dedicated `realsense-baseline-rollback` Environment deployment. The workflow:

1. verifies the complete ledger hash chain;
2. requires the digest to reference a prior `PROMOTE` entry;
3. verifies the archived file digest and native baseline safety contract;
4. restores it as `realsense-native-baseline.json`;
5. appends a `ROLLBACK` entry;
6. opens a reviewable PR without pushing to the default branch.

Rollback is a new auditable state transition; historical entries are never
removed. Robot motion remains disabled throughout. Branch protection should
require review of the baseline, archive, and ledger changes together.

## B2-B3B3A signed ledger anchor

Each governance PR also updates `realsense-baseline-ledger-anchor.json`. The
anchor binds the ledger byte digest, entry count, head digest, active baseline
digest, action, commit, timestamp, and workflow run. The protected job creates
a GitHub artifact attestation for that exact JSON and immediately verifies it.

Before the next promotion or rollback, the job verifies the previous anchor's
GitHub attestation and compares it with the checked-out default branch. A
missing anchor for a non-empty ledger, shortened/replaced ledger tail, changed
ledger bytes, or swapped active baseline blocks governance before mutation.
Only an empty ledger may bootstrap without an earlier anchor.
