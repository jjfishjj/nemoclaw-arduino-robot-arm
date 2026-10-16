# AI agent handoff

## Mission

Maintain one ML fine-tuning workflow that can move between Google Colab, Hugging Face Jobs, GPUtw, and RunPod without forking the training code.

## Current state

- Common trainer supports QLoRA, LoRA, and full fine-tuning.
- Platform adapters cover Colab, HF Jobs, and generic GPU hosts/containers used by GPUtw and RunPod.
- Local complete-checkpoint discovery and Hugging Face Hub `last-checkpoint` fallback are implemented.
- Configuration, checkpoint selection, and training helper logic have dependency-free unit tests.
- The repository includes a short QLoRA smoke configuration and a Colab notebook.
- Static checks, nine unit tests, and dry-run validation pass on macOS without CUDA.

This is an implementation-ready template, not yet a GPU-certified release. No real CUDA training run has been recorded in this repository.

## Entry points

| Purpose | File or command |
|---|---|
| User guide | `README.md` |
| Training configuration | `configs/qlora-smoke.json` |
| Shared launch command | `./scripts/run.sh` |
| Trainer | `src/train.py` |
| GPU host adapter | `scripts/platforms/run_gpu_host.sh` |
| Docker GPU adapter | `scripts/platforms/run_docker_gpu.sh` |
| HF Jobs submission | `scripts/platforms/submit_hf_job.sh` |
| Colab workflow | `notebooks/colab.ipynb` |

## Verified commands

Run from `portable-ml-training/`:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src scripts tests
bash -n scripts/run.sh scripts/platforms/*.sh
python -m json.tool configs/qlora-smoke.json >/dev/null
python -m json.tool notebooks/colab.ipynb >/dev/null
./scripts/run.sh --dry-run
python scripts/preflight.py --config configs/qlora-smoke.json --allow-cpu
```

## Next milestone: GPU smoke certification

The next agent should run the default configuration for 20 steps on one supported NVIDIA GPU, then prove that a stopped run resumes from the latest complete checkpoint.

Acceptance checklist:

- [ ] Record platform, GPU model/count, VRAM, driver, CUDA, Python, PyTorch, Transformers, PEFT, and bitsandbytes versions.
- [ ] Run `python scripts/preflight.py --config configs/qlora-smoke.json` successfully.
- [ ] Run the 20-step QLoRA smoke job and retain logs outside Git.
- [ ] Confirm a complete `checkpoint-N` is created on persistent storage.
- [ ] Restart the same command and confirm automatic resume.
- [ ] If `HF_MODEL_ID` is configured, confirm `last-checkpoint` and the final adapter are uploaded.
- [ ] Record wall time, peak VRAM, and estimated platform cost in this document or a linked issue/PR.
- [ ] Open follow-up issues for platform-specific mount paths or image incompatibilities instead of branching the common trainer prematurely.

## Suggested follow-on stages

1. **GPU smoke certification (recommended):** use the smallest paid run that validates CUDA, checkpoint, and resume behavior.
2. **Container publishing:** add a GHCR workflow after the smoke run establishes a working dependency set.
3. **Benchmark matrix:** test the same model/config on available GPU types, then update the cost calculator using measured throughput rather than advertised hourly price alone.
4. **Production hardening:** pin a tested lockfile/image digest, add dataset validation, structured logs, and failure notifications.

## Secrets and generated data

Use environment variables or platform secret stores for `HF_TOKEN` and private dataset credentials. Do not commit tokens, `.env`, checkpoints, model weights, Hub caches, logs, or training datasets. The included `.gitignore` covers the expected local outputs, but agents must still inspect staged files before committing.
