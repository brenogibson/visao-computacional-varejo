#!/bin/bash
# Pipeline B — Eixo B2: 6 modelos gerenciados × {referência, principal} @ 0,5 fps (taxa vencedora do B1).
# Instância CPU (inferência no Bedrock). AUTO-TERMINA. Saídas: s3://$BUCKET/runs/b2ext/.
set -euo pipefail
exec > /var/log/tcc-b2.log 2>&1

BUCKET=video-analytics-store
REGION=us-east-1
echo "=== TCC B2-ext job (gemma-31b + grok-4.6): $(date -u) ==="
apt-get update -q && apt-get install -y -q ffmpeg zip python3-venv python3-pip unzip curl
command -v aws >/dev/null || { curl -sS https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/awscli.zip && unzip -q /tmp/awscli.zip -d /tmp && /tmp/aws/install; }

WORK=/opt/tcc && mkdir -p $WORK && cd $WORK
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q anthropic openai boto3 aws-bedrock-token-generator

aws s3 cp s3://$BUCKET/videos/derived/ref_5fps.mp4 ref_5fps.mp4 --region $REGION --only-show-errors
aws s3 cp s3://$BUCKET/videos/derived/main_5fps.mp4 main_5fps.mp4 --region $REGION --only-show-errors
aws s3 cp s3://$BUCKET/code/retailcv_src.tar.gz src.tar.gz --region $REGION --only-show-errors
tar xzf src.tar.gz

cat > run_b2.py <<'PYEOF'
import json, sys
sys.path.insert(0, "src")
from retailcv.pipeline_b.runner import run_model

MODELS = [
    
    
    
    
    
    "google.gemma-4-31b",
    "us.xai.grok-4.6",
]
VIDEOS = [("ref_5fps.mp4", "ref"), ("main_5fps.mp4", "main")]
FPS = 0.5  # taxa vencedora do B1 (critério pré-registrado)

summaries = []
for video, key in VIDEOS:
    for model in MODELS:
        tag = f"{key}_{model.split('.')[-1]}"
        try:
            s = run_model(video, key, model, FPS, f"b2_out/{tag}", workers=10)
            summaries.append(s)
            print("B2:", json.dumps(s), flush=True)
        except Exception as e:
            summaries.append({"model_id": model, "video_key": key, "fatal_error": str(e)[:300]})
            print(f"B2 FATAL: {model} {key}: {e}", flush=True)
        json.dump(summaries, open("b2_summaries.json", "w"), indent=1)

PYEOF
./venv/bin/python run_b2.py

zip -qr b2_out.zip b2_out
aws s3 cp b2_out.zip s3://$BUCKET/runs/b2ext/b2_out.zip --region $REGION --only-show-errors
aws s3 cp b2_summaries.json s3://$BUCKET/runs/b2ext/b2_summaries.json --region $REGION --only-show-errors
aws s3 cp /var/log/tcc-b2.log s3://$BUCKET/runs/b2ext/job_log.txt --region $REGION --only-show-errors || true

echo "=== done: $(date -u) — shutting down ==="
shutdown -h now
