#!/bin/bash
# Fase A1 — Triagem: detecção 1x (cache) + 7 trackers sobre o vídeo de referência (5 fps).
# Roda em EC2 g6.xlarge (D13: 100% nuvem) e AUTO-TERMINA. Saídas em s3://$BUCKET/runs/screening/.
set -euo pipefail
exec > /var/log/tcc-screening.log 2>&1

BUCKET=video-analytics-store
REGION=us-east-1
echo "=== TCC screening job: $(date -u) ==="
apt-get update -q && apt-get install -y -q ffmpeg zip
nvidia-smi -L

WORK=/opt/tcc && mkdir -p $WORK && cd $WORK
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128
./venv/bin/pip install -q ultralytics==8.4.106 boxmot opencv-python-headless numpy

aws s3 cp s3://$BUCKET/videos/derived/ref_5fps.mp4 ref_5fps.mp4 --region $REGION --only-show-errors
aws s3 cp s3://$BUCKET/code/retailcv_src.tar.gz src.tar.gz --region $REGION --only-show-errors
tar xzf src.tar.gz

cat > run_screening.py <<'PYEOF'
import json, sys, time
sys.path.insert(0, "src")
from retailcv.detect import detect_video, load_cache
from retailcv.track import track_video

TRACKERS = ["bytetrack", "ocsort", "botsort", "deepocsort", "strongsort", "boosttrack", "hybridsort"]

results = {"job": "screening_A1", "detector": {}, "trackers": []}

det_stats = detect_video("ref_5fps.mp4", "det_cache_ref.npz", model_name="yolo26m.pt", conf=0.25)
results["detector"] = det_stats
print("DETECT:", det_stats, flush=True)

cache = load_cache("det_cache_ref.npz")
for name in TRACKERS:
    try:
        st = track_video("ref_5fps.mp4", cache, name, f"trackers_out/{name}/ref.txt")
        results["trackers"].append(st)
        print("TRACK :", st, flush=True)
    except Exception as e:
        results["trackers"].append({"tracker": name, "error": str(e)[:300]})
        print(f"ERRO  : {name}: {e}", flush=True)

json.dump(results, open("screening_stats.json", "w"), indent=1)
PYEOF
./venv/bin/python run_screening.py

zip -qr trackers_out.zip trackers_out
aws s3 cp trackers_out.zip s3://$BUCKET/runs/screening/trackers_out.zip --region $REGION --only-show-errors
aws s3 cp det_cache_ref.npz s3://$BUCKET/runs/screening/det_cache_ref.npz --region $REGION --only-show-errors
aws s3 cp screening_stats.json s3://$BUCKET/runs/screening/screening_stats.json --region $REGION --only-show-errors
aws s3 cp /var/log/tcc-screening.log s3://$BUCKET/runs/screening/job_log.txt --region $REGION --only-show-errors || true

echo "=== done: $(date -u) — shutting down ==="
shutdown -h now
