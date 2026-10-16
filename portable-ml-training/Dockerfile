FROM pytorch/pytorch:2.7.1-cuda12.8-cudnn9-runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/data/hf-cache \
    ML_WORKDIR=/data/checkpoints

WORKDIR /workspace
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY configs ./configs
COPY src ./src
COPY scripts ./scripts
RUN chmod +x scripts/run.sh scripts/platforms/*.sh

CMD ["/workspace/scripts/run.sh"]
