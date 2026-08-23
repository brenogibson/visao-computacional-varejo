#!/bin/bash
# Pipeline B — modelo open-weights SELF-HOSTED: Qwen3-VL-8B-Instruct-FP8 via vLLM em g6.xlarge (L4).
# Sobe o servidor local, roda ref+main @ 0,5 fps com o mesmo runner/schema, mede tempos.
# Custo = horas de instância (não tokens). AUTO-TERMINA. Saídas: s3://$BUCKET/runs/qwen/.
set -euo pipefail
exec > /var/log/tcc-qwen.log 2>&1

BUCKET=video-analytics-store
REGION=us-east-1
MODEL="Qwen/Qwen3-VL-8B-Instruct-FP8"
echo "=== TCC Qwen job: $(date -u) ==="
apt-get update -q && apt-get install -y -q ffmpeg zip
nvidia-smi -L

WORK=/opt/tcc && mkdir -p $WORK && cd $WORK
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q vllm openai boto3 aws-bedrock-token-generator anthropic

aws s3 cp s3://$BUCKET/videos/derived/ref_5fps.mp4 ref_5fps.mp4 --region $REGION --only-show-errors
aws s3 cp s3://$BUCKET/videos/derived/main_5fps.mp4 main_5fps.mp4 --region $REGION --only-show-errors
aws s3 cp s3://$BUCKET/code/retailcv_src.tar.gz src.tar.gz --region $REGION --only-show-errors
tar xzf src.tar.gz

# sobe o vLLM em background e espera ficar pronto
SETUP_T0=$(date +%s)
./venv/bin/vllm serve "$MODEL" --max-model-len 8192 --limit-mm-per-prompt '{"image": 1}' \
  --gpu-memory-utilization 0.92 > /var/log/vllm.log 2>&1 &
for i in $(seq 1 120); do
  curl -s -o /dev/null http://localhost:8000/v1/models && break
  sleep 15
done
SETUP_WALL=$(( $(date +%s) - SETUP_T0 ))
echo "vllm pronto em ${SETUP_WALL}s"

cat > run_qwen.py <<PYEOF
import json, sys
sys.path.insert(0, "src")
from retailcv.pipeline_b.runner import run_model

summaries = {"server_setup_s": ${SETUP_WALL}}
for video, key in [("ref_5fps.mp4", "ref"), ("main_5fps.mp4", "main")]:
    s = run_model(video, key, "local/${MODEL}", 0.5, f"qwen_out/{key}", workers=4)
    summaries[key] = s
    print("QWEN:", json.dumps(s), flush=True)
json.dump(summaries, open("qwen_summaries.json", "w"), indent=1)
PYEOF
./venv/bin/python run_qwen.py

zip -qr qwen_out.zip qwen_out
aws s3 cp qwen_out.zip s3://$BUCKET/runs/qwen/qwen_out.zip --region $REGION --only-show-errors
aws s3 cp qwen_summaries.json s3://$BUCKET/runs/qwen/qwen_summaries.json --region $REGION --only-show-errors
aws s3 cp /var/log/vllm.log s3://$BUCKET/runs/qwen/vllm_log.txt --region $REGION --only-show-errors || true
aws s3 cp /var/log/tcc-qwen.log s3://$BUCKET/runs/qwen/job_log.txt --region $REGION --only-show-errors || true

echo "=== done: $(date -u) — shutting down ==="
shutdown -h now
