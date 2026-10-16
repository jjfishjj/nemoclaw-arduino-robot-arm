# Agent instructions

This directory is an independently testable, portable ML training template. Keep changes scoped to `portable-ml-training/` unless a repository-level CI change is required.

## Start here

1. Read `README.md` for supported platforms and user-facing commands.
2. Read `HANDOFF.md` for current status, known limitations, and the next milestone.
3. Run the dependency-free checks before editing:

   ```bash
   python -m unittest discover -s tests -v
   ./scripts/run.sh --dry-run
   ```

## Change rules

- Keep training behavior in `src/`; platform scripts should only set mounts, environment variables, and launch the common trainer.
- Never commit `.env`, access tokens, model weights, datasets, checkpoints, or generated training output.
- Preserve checkpoint compatibility and the `resume.mode` behavior documented in `README.md`.
- Avoid making GPU vendor/platform assumptions in the common trainer.
- Add or update standard-library unit tests for logic that does not require a GPU.
- Treat prices, GPU availability, and platform product details as time-sensitive; verify them from official sources before documenting them.

## Required validation

Run all checks that apply:

```bash
python -m json.tool configs/qlora-smoke.json >/dev/null
python -m json.tool notebooks/colab.ipynb >/dev/null
bash -n scripts/run.sh scripts/platforms/*.sh
python -m compileall -q src scripts tests
python -m unittest discover -s tests -v
./scripts/run.sh --dry-run
```

Actual CUDA training is a separate acceptance step and must record the GPU type, image or package versions, command, elapsed time, peak VRAM, and checkpoint/resume result.
