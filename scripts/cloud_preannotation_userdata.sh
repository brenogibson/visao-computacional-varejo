#!/bin/bash
# Job de pré-anotação do ground truth (Fase 1) — roda em EC2 g6.xlarge e AUTO-TERMINA.
# Conforme D06: pré-anota com yolo26x (variante DIFERENTE da avaliada, yolo26m) + ByteTrack.
# Saídas no S3: videos/derived/ref_5fps.mp4 + annotations/preanno/preanno_mot.zip + log.
set -euo pipefail
exec > /var/log/tcc-preanno.log 2>&1

BUCKET=video-analytics-store
REGION=us-east-1
echo "=== TCC pre-annotation job: $(date -u) ==="
# A DLAMI Base NÃO traz ffmpeg/zip — instalar sempre (falha de 26/07 documentada no DIARIO)
apt-get update -q && apt-get install -y -q ffmpeg zip
nvidia-smi -L

WORK=/opt/tcc && mkdir -p $WORK && cd $WORK
python3 -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cu128
./venv/bin/pip install -q ultralytics==8.4.106 boxmot opencv-python-headless numpy

aws s3 cp s3://$BUCKET/blurredvideo.mp4 ref.mp4 --region $REGION --only-show-errors

# Sequência oficial: 5 fps (D05)
ffmpeg -v error -i ref.mp4 -vf fps=5 -c:v libx264 -crf 18 ref_5fps.mp4 -y
aws s3 cp ref_5fps.mp4 s3://$BUCKET/videos/derived/ref_5fps.mp4 --region $REGION --only-show-errors

cat > preanno.py <<'PYEOF'
import time
import numpy as np
from ultralytics import YOLO
from boxmot.trackers.registry import create_tracker
import cv2

t0 = time.time()
model = YOLO("yolo26x.pt")  # variante x, threshold baixo (D06 — anti-viés)
tracker = create_tracker("bytetrack", reid_weights=None, device="cuda:0", half=True)

cap = cv2.VideoCapture("ref_5fps.mp4")
KEYSTEP = 5  # 1 keyframe/segundo a 5 fps -> keyframes esparsos p/ interpolar no CVAT
lines = []
fi = 0
while True:
    ok, frame = cap.read()
    if not ok:
        break
    fi += 1  # MOT e' 1-based
    r = model.predict(frame, classes=[0], conf=0.15, verbose=False)[0]
    dets = np.hstack([r.boxes.xyxy.cpu().numpy(),
                      r.boxes.conf.cpu().numpy()[:, None],
                      r.boxes.cls.cpu().numpy()[:, None]]).astype(np.float32) \
        if len(r.boxes) else np.empty((0, 6), dtype=np.float32)
    tracks = tracker.update(dets, frame)
    if (fi - 1) % KEYSTEP:
        continue
    for x1, y1, x2, y2, tid, conf, cls, _ in tracks:
        lines.append(f"{fi},{int(tid)},{x1:.1f},{y1:.1f},{x2-x1:.1f},{y2-y1:.1f},1,1,1.0")
cap.release()
open("gt.txt", "w").write("\n".join(lines) + "\n")
wall = time.time() - t0
print(f"frames={fi} keyframe_boxes={len(lines)} wall={wall:.1f}s ({fi/wall:.1f} fps proc)")
open("job_stats.txt", "w").write(f"frames={fi}\nkeyframe_boxes={len(lines)}\nwall_s={wall:.1f}\nfps_proc={fi/wall:.2f}\n")
PYEOF
./venv/bin/python preanno.py

mkdir -p gt && mv gt.txt gt/ && echo "person" > gt/labels.txt
zip -qr preanno_mot.zip gt
aws s3 cp preanno_mot.zip s3://$BUCKET/annotations/preanno/preanno_mot.zip --region $REGION --only-show-errors
aws s3 cp job_stats.txt s3://$BUCKET/annotations/preanno/job_stats.txt --region $REGION --only-show-errors
aws s3 cp /var/log/tcc-preanno.log s3://$BUCKET/annotations/preanno/job_log.txt --region $REGION --only-show-errors || true

echo "=== done: $(date -u) — shutting down ==="
shutdown -h now
