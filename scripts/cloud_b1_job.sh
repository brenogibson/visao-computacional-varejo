#!/bin/bash
# Pipeline B — Eixo B1 (calibração da taxa de amostragem) no vídeo de referência.
# 3 taxas (0.5 / 1 / 2 fps) × 2 modelos econômicos (Claude Haiku 4.5 + GPT-5.6 Luna).
# Instância CPU (a inferência MLLM acontece no Bedrock; aqui só orquestração — D13 ok).
# AUTO-TERMINA. Saídas: s3://$BUCKET/runs/b1/.
set -euo pipefail
exec > /var/log/tcc-b1.log 2>&1

BUCKET=video-analytics-store
REGION=us-east-1
echo "=== TCC B1 job: $(date -u) ==="
apt-get update -q && apt-get install -y -q ffmpeg zip python3-venv python3-pip unzip curl
command -v aws >/dev/null || { curl -sS https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip && unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install; }

WORK=/opt/tcc && mkdir -p $WORK && cd $WORK
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q anthropic openai boto3 aws-bedrock-token-generator

aws s3 cp s3://$BUCKET/videos/derived/ref_5fps.mp4 ref_5fps.mp4 --region $REGION --only-show-errors
aws s3 cp s3://$BUCKET/code/retailcv_src.tar.gz src.tar.gz --region $REGION --only-show-errors
tar xzf src.tar.gz

cat > run_b1.py <<'PYEOF'
import json, sys
sys.path.insert(0, "src")
from retailcv.pipeline_b.runner import run_model

MODELS = ["anthropic.claude-haiku-4-5", "openai.gpt-5.6-luna"]
RATES = [0.5, 1.0, 2.0]

summaries = []
for model in MODELS:
    for fps in RATES:
        tag = f"{model.split('.')[-1]}_{fps}fps".replace(".", "p", 1) if False else f"{model.split('.')[-1]}_fps{fps}"
        s = run_model("ref_5fps.mp4", "ref", model, fps, f"b1_out/{tag}", workers=8)
        summaries.append(s)
        print("B1:", json.dumps(s), flush=True)

json.dump(summaries, open("b1_summaries.json", "w"), indent=1)
PYEOF
./venv/bin/python run_b1.py

zip -qr b1_out.zip b1_out
aws s3 cp b1_out.zip s3://$BUCKET/runs/b1/b1_out.zip --region $REGION --only-show-errors
aws s3 cp b1_summaries.json s3://$BUCKET/runs/b1/b1_summaries.json --region $REGION --only-show-errors
aws s3 cp /var/log/tcc-b1.log s3://$BUCKET/runs/b1/job_log.txt --region $REGION --only-show-errors || true

echo "=== done: $(date -u) — shutting down ==="
shutdown -h now
