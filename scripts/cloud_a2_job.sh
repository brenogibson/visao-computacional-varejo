#!/bin/bash
# Fase A2 — Eixos experimentais no vídeo PRINCIPAL (37 min) com os 2 finalistas.
# E0 baseline | E1 somente-detecção | E2 ablação incremental (P0..P4) | E3 ReID.
# + A3 parcial: detecção+tracking no vídeo de escalabilidade (67 min) p/ custo/linearidade.
# EC2 g6.xlarge, auto-terminante (D13). Saídas: s3://$BUCKET/runs/a2/.
set -euo pipefail
exec > /var/log/tcc-a2.log 2>&1

BUCKET=video-analytics-store
REGION=us-east-1
MAIN_KEY="WJCI3607077HN_2_1777749037992.mp4.mp4"
SCALE_KEY="WJCI3607077HN_2_1777752446477.mp4.mp4"
echo "=== TCC A2 job: $(date -u) ==="
apt-get update -q && apt-get install -y -q ffmpeg zip
nvidia-smi -L

WORK=/opt/tcc && mkdir -p $WORK && cd $WORK
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128
./venv/bin/pip install -q ultralytics==8.4.106 boxmot opencv-python-headless numpy

aws s3 cp "s3://$BUCKET/$MAIN_KEY" main_raw.mp4 --region $REGION --only-show-errors
aws s3 cp "s3://$BUCKET/$SCALE_KEY" scale_raw.mp4 --region $REGION --only-show-errors
aws s3 cp s3://$BUCKET/code/retailcv_src.tar.gz src.tar.gz --region $REGION --only-show-errors
tar xzf src.tar.gz

# Sequências oficiais a 5 fps (D05/D11 — reamostragem por tempo)
ffmpeg -v error -i main_raw.mp4 -vf fps=5 -c:v libx264 -crf 18 main_5fps.mp4 -y
ffmpeg -v error -i scale_raw.mp4 -vf fps=5 -c:v libx264 -crf 18 scale_5fps.mp4 -y
aws s3 cp main_5fps.mp4 s3://$BUCKET/videos/derived/main_5fps.mp4 --region $REGION --only-show-errors
aws s3 cp scale_5fps.mp4 s3://$BUCKET/videos/derived/scale_5fps.mp4 --region $REGION --only-show-errors

cat > run_a2.py <<'PYEOF'
import json, sys, time
sys.path.insert(0, "src")
from retailcv.detect import detect_video, load_cache
from retailcv.track import track_video
from retailcv.postprocess import run_incremental
from retailcv.reid_gallery import run_reid

FINALISTS = ["bytetrack", "hybridsort"]
results = {"job": "a2_axes", "detect": {}, "e0_tracking": [], "e2_postprocess": {}, "e3_reid": {}, "a3_scale": {}}

# --- E1/base: detecção com cache (o próprio cache É o modo somente-detecção) ---
for vid in ["main", "scale"]:
    st = detect_video(f"{vid}_5fps.mp4", f"det_{vid}.npz", model_name="yolo26m.pt", conf=0.25)
    results["detect"][vid] = st
    print("DETECT:", vid, st, flush=True)

cache_main = load_cache("det_main.npz")

# --- E0: finalistas puros no vídeo principal ---
for name in FINALISTS:
    st = track_video("main_5fps.mp4", cache_main, name, f"a2_out/{name}/E0.txt")
    results["e0_tracking"].append(st)
    print("E0:", st, flush=True)

# --- E2: ablação incremental sobre a saída E0 de cada finalista (CPU, barato) ---
for name in FINALISTS:
    logs = run_incremental(f"a2_out/{name}/E0.txt", f"a2_out/{name}/E2")
    results["e2_postprocess"][name] = logs
    print("E2:", name, logs, flush=True)

# --- E3: ReID (teto de custo) sobre o melhor estágio E2 (P4) ---
for name in FINALISTS:
    t0 = time.time()
    st = run_reid("main_5fps.mp4", f"a2_out/{name}/E2/P4_stitch.txt",
                  f"a2_out/{name}/E3_reid.txt", reid_weights="osnet_x1_0_msmt17.pt")
    st["wall_s"] = round(time.time() - t0, 1)
    results["e3_reid"][name] = st
    print("E3:", name, st, flush=True)

# --- A3: melhor finalista da triagem (bytetrack) no vídeo de escalabilidade ---
cache_scale = load_cache("det_scale.npz")
st = track_video("scale_5fps.mp4", cache_scale, "bytetrack", "a2_out/scale/bytetrack.txt")
results["a3_scale"] = st
print("A3:", st, flush=True)

json.dump(results, open("a2_stats.json", "w"), indent=1)
PYEOF
./venv/bin/python run_a2.py

zip -qr a2_out.zip a2_out
aws s3 cp a2_out.zip s3://$BUCKET/runs/a2/a2_out.zip --region $REGION --only-show-errors
aws s3 cp det_main.npz s3://$BUCKET/runs/a2/det_main.npz --region $REGION --only-show-errors
aws s3 cp det_scale.npz s3://$BUCKET/runs/a2/det_scale.npz --region $REGION --only-show-errors
aws s3 cp a2_stats.json s3://$BUCKET/runs/a2/a2_stats.json --region $REGION --only-show-errors
aws s3 cp /var/log/tcc-a2.log s3://$BUCKET/runs/a2/job_log.txt --region $REGION --only-show-errors || true

echo "=== done: $(date -u) — shutting down ==="
shutdown -h now
