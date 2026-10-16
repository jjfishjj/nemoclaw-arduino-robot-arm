# Colab／HF Jobs／GPUtw／RunPod 共用 ML 訓練模板

同一份 `configs/qlora-smoke.json` 與 `src/train.py` 可在四種 GPU 環境執行。平台腳本只負責掛載持久儲存、設定環境變數與啟動；模型、dataset、QLoRA、checkpoint 與 Hub 上傳邏輯維持一份。

交接給其他 AI agent 時，請先閱讀 [`HANDOFF.md`](HANDOFF.md)；agent 的修改與驗證規則在 [`AGENTS.md`](AGENTS.md)。

## 已包含

- QLoRA 4-bit、LoRA 與 full fine-tuning 三種模式。
- 單 GPU 或 `torchrun` 多 GPU 啟動。
- 定期 checkpoint、自動找到最新完整 checkpoint、排除未寫完的 JIT checkpoint。
- 支援 Transformers 新版 JIT checkpoint（安裝版本支援時自動開啟）。
- HF Hub `last-checkpoint` 下載續訓及完成後 adapter 上傳。
- Google Drive、RunPod Volume 或 GPUtw 掛載磁碟持久化。
- 不載入模型的 `--dry-run`、GPU preflight 與標準函式庫單元測試。
- Token 不寫入設定檔或映像檔，只由 `HF_TOKEN` 注入。

## 1. 先做本機設定檢查

這一步不需要安裝 PyTorch：

```bash
cd portable-ml-training
./scripts/run.sh --dry-run
python -m unittest discover -s tests -v
```

真正訓練前：

```bash
python -m pip install -r requirements.txt
export HF_TOKEN=hf_xxx
export HF_MODEL_ID=your-user/qwen-portable-qlora  # 選填；設定後會啟用 Hub 上傳
./scripts/run.sh
```

預設設定只跑 20 steps，適合驗證整條 pipeline。正式訓練前請複製設定檔，調高 `max_steps` 或改用 `epochs`。

## 2. 共通設定

主要可調欄位：

| 區塊 | 重要欄位 |
|---|---|
| `model` | 模型 ID、最大序列長度 |
| `dataset` | Hub dataset、split、文字欄位或 prompt/response 欄位 |
| `method` | `qlora`、`lora`、`full` 與 LoRA 參數 |
| `training` | batch、gradient accumulation、steps、checkpoint 頻率 |
| `output` | 本機目錄、Hub repo 與 `hub_strategy` |
| `resume` | `auto`、`never` 或 `path:/...` |

環境變數優先於 JSON：

- `ML_WORKDIR`：將輸出改到持久磁碟下。
- `HF_MODEL_ID`：設定 Hub repo 並自動啟用 push。
- `ML_MAX_STEPS`：臨時覆寫 steps，適合 smoke test。
- `NUM_GPUS`：大於 1 時使用 `torchrun`。
- `ML_PLATFORM`：`colab`、`huggingface`、`gputw` 或 `runpod`。

## 3. Colab

開啟 [`notebooks/colab.ipynb`](notebooks/colab.ipynb)，先把 `REPO_URL` 換成你的 Git repository。Notebook 會：

1. 掛載 Google Drive。
2. 安裝依賴。
3. 把 `ML_WORKDIR` 與 `HF_HOME` 指到 Drive。
4. 先 dry run，再開始訓練。

Colab 可能回收 runtime；checkpoint 頻率不要設得過疏。

## 4. Hugging Face Jobs

先建立並推送映像：

```bash
docker build -t ghcr.io/YOUR_USER/portable-ml-training:latest .
docker push ghcr.io/YOUR_USER/portable-ml-training:latest
```

登入 HF CLI、設定必要變數並提交：

```bash
hf auth login
export TRAINING_IMAGE=ghcr.io/YOUR_USER/portable-ml-training:latest
export HF_MODEL_ID=your-user/qwen-portable-qlora
export HF_FLAVOR=a10g-large
./scripts/platforms/submit_hf_job.sh
```

Jobs 的本機磁碟是暫時性的，因此應設定 `HF_MODEL_ID`。模板使用 `hub_strategy=checkpoint`，新 Job 若沒有本機 checkpoint，會嘗試下載 Hub 的 `last-checkpoint`。

## 5. GPUtw／RunPod：直接在 GPU 主機執行

在持久磁碟中保留 checkpoint 與 HF cache：

```bash
export ML_PLATFORM=gputw                  # RunPod 改成 runpod
export PERSISTENT_ROOT=/mnt/persistent/ml # 換成平台實際掛載點
export HF_TOKEN=hf_xxx
export HF_MODEL_ID=your-user/qwen-portable-qlora  # 選填但建議
export NUM_GPUS=1
./scripts/platforms/run_gpu_host.sh
```

若平台提供 Docker：

```bash
export TRAINING_IMAGE=ghcr.io/YOUR_USER/portable-ml-training:latest
export ML_PLATFORM=runpod
export PERSISTENT_ROOT=/workspace/ml-data
export HF_TOKEN=hf_xxx
./scripts/platforms/run_docker_gpu.sh
```

GPUtw 的實際 mount path、SSH 帳號與 image 啟動方式需以租用主機資訊為準；訓練程式本身不依賴平台 API。

## 6. 續訓規則

優先順序：

1. `resume.mode=path:/...` 指定 checkpoint。
2. `resume.mode=auto` 尋找本機最新且完整的 `checkpoint-N`。
3. 本機沒有、已設定 Hub repo 與 token 時，下載 `last-checkpoint`。
4. 都沒有則從頭訓練。

若目錄含 `checkpoint-is-incomplete.txt`，模板不會從該 checkpoint 續訓。

## 7. 安全與限制

- 不要把 `.env`、HF token 或私有 dataset credentials commit 進 Git。
- 多張 GPU 並不會自動讓模型適配；QLoRA 多卡仍需依模型與拓撲測試。
- 本模板提供容量與執行流程，不保證不同 GPU 的吞吐；正式成本要以小批次 benchmark 更新。
- 在 RunPod Community 或可被回收的資源上，務必使用持久磁碟或 Hub checkpoint。

官方依據：

- Hugging Face Trainer resume：<https://huggingface.co/docs/transformers/en/main_classes/trainer>
- PEFT QLoRA：<https://huggingface.co/docs/peft/developer_guides/quantization>
- Hugging Face Jobs：<https://huggingface.co/docs/huggingface_hub/guides/jobs>
