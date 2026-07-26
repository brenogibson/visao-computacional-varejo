"""Detecção de pessoas com cache — roda YOLO26 UMA vez por vídeo e salva as detecções.

Todos os trackers da triagem consomem o MESMO cache (paridade perfeita: mesmas
detecções para todos) e a GPU não é gasta 7 vezes (seção 5 do plano).

Formato do cache (.npz): para cada frame i, array (N,6) [x1,y1,x2,y2,conf,cls].
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np


def detect_video(video: str | Path, out_npz: str | Path, model_name: str = "yolo26m.pt",
                 conf: float = 0.25, device: str = "cuda:0") -> dict:
    from ultralytics import YOLO

    model = YOLO(model_name)
    cap = cv2.VideoCapture(str(video))
    per_frame: list[np.ndarray] = []
    t0 = time.time()
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        r = model.predict(frame, classes=[0], conf=conf, device=device, verbose=False)[0]
        dets = np.hstack([
            r.boxes.xyxy.cpu().numpy(),
            r.boxes.conf.cpu().numpy()[:, None],
            r.boxes.cls.cpu().numpy()[:, None],
        ]).astype(np.float32) if len(r.boxes) else np.empty((0, 6), dtype=np.float32)
        per_frame.append(dets)
    cap.release()
    wall = time.time() - t0

    np.savez_compressed(out_npz, n_frames=len(per_frame),
                        **{f"f{i:06d}": d for i, d in enumerate(per_frame)})
    stats = {"model": model_name, "conf": conf, "frames": len(per_frame),
             "wall_s": round(wall, 1), "fps_proc": round(len(per_frame) / wall, 1),
             "total_boxes": int(sum(len(d) for d in per_frame))}
    return stats


def load_cache(npz_path: str | Path) -> list[np.ndarray]:
    z = np.load(npz_path)
    n = int(z["n_frames"])
    return [z[f"f{i:06d}"] for i in range(n)]
