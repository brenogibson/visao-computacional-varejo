#!/bin/bash
# Etapa agêntica (D17): bateria de 10 perguntas × 2 pipelines, sessões separadas. AUTO-TERMINA.
set -euo pipefail
exec > /var/log/tcc-insights.log 2>&1
BUCKET=video-analytics-store
REGION=us-east-1
apt-get update -q && apt-get install -y -q python3-venv python3-pip unzip curl zip
command -v aws >/dev/null || { curl -sS https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o /tmp/a.zip && unzip -q /tmp/a.zip -d /tmp && /tmp/aws/install; }
WORK=/opt/tcc && mkdir -p $WORK && cd $WORK
python3 -m venv venv && ./venv/bin/pip install -q --upgrade pip && ./venv/bin/pip install -q anthropic boto3
aws s3 cp s3://$BUCKET/code/retailcv_src.tar.gz src.tar.gz --region $REGION --only-show-errors && tar xzf src.tar.gz
aws s3 cp s3://$BUCKET/pipeline-b/insights/insights_dataset_A.json . --region $REGION --only-show-errors
aws s3 cp s3://$BUCKET/pipeline-b/insights/insights_dataset_B.json . --region $REGION --only-show-errors
cat > run_insights.py <<'PYEOF'
import json, sys
sys.path.insert(0, "src")
from retailcv.insights.agent import run_battery
out = {"A": run_battery("insights_dataset_A.json"), "B": run_battery("insights_dataset_B.json")}
json.dump(out, open("insights_results.json", "w"), ensure_ascii=False, indent=1)
PYEOF
./venv/bin/python run_insights.py
aws s3 cp insights_results.json s3://$BUCKET/runs/insights/insights_results.json --region $REGION --only-show-errors
aws s3 cp /var/log/tcc-insights.log s3://$BUCKET/runs/insights/job_log.txt --region $REGION --only-show-errors || true
shutdown -h now
