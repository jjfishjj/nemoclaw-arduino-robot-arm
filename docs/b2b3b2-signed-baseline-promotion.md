# B2-B3B2 — Signed RealSense baseline promotion

The manual workflow separates hardware capture from repository mutation:

1. A default-branch-only `realsense` self-hosted runner generates a native
   candidate with read-only repository permissions and no persisted checkout
   credentials.
2. The candidate is uploaded as a short-lived workflow artifact.
3. A GitHub-hosted job pauses at the `realsense-baseline-promotion` Environment.
4. After a required reviewer approves it, the job validates the fixed sampling,
   filter, native verification, motion, hash, and metric contracts.
5. `actions/attest@v4` creates signed build provenance and `gh attestation
   verify` verifies it immediately.
6. The job opens a `codex/realsense-baseline-*` pull request. It never pushes to
   the default branch directly.

Repository administrators must create the `realsense-baseline-promotion`
Environment and configure required reviewers. Without that protection, naming
the Environment in YAML does not itself create an approval requirement.

Artifact attestations require a public repository on GitHub Free/Pro/Team, or
GitHub Enterprise Cloud for private/internal repositories. Verify a downloaded
candidate later with:

```bash
gh attestation verify realsense-native-baseline.json --repo OWNER/REPOSITORY
```

The committed baseline changes only after the generated PR passes normal review
and merge protection. Baseline capture and validation never enable robot motion.
