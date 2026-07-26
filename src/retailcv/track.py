"""Tracking sobre cache de detecções — um tracker por execução, saída MOT Challenge.

Os trackers com ReID (botsort, strongsort, deepocsort, boosttrack, hybridsort)
precisam dos frames para extrair descritores de aparência; os motion-only
(bytetrack, ocsort) usam apenas as caixas. Em ambos os casos as DETECÇÕES vêm
do cache — o detector nunca roda de novo.
"""
from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np

MOTION_ONLY = {"bytetrack", "ocsort"}
REID_WEIGHTS_DEFAULT = "osnet_x0_25_msmt17.pt"  # leve p/ triagem; osnet_x1_0 no eixo ReID


def track_video(video: str | Path, det_cache: list[np.ndarray], tracker_name: str,
                out_txt: str | Path, device: str = "cuda:0",
                reid_weights: str = REID_WEIGHTS_DEFAULT) -> dict:
    from boxmot.trackers.registry import create_tracker

    kwargs = {"device": device, "half": True}
    kwargs["reid_weights"] = None if tracker_name in MOTION_ONLY else Path(reid_weights)
    tracker = create_tracker(tracker_name, **kwargs)

    cap = cv2.VideoCapture(str(video))
    lines: list[str] = []
    t0 = time.time()
    fi = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        dets = det_cache[fi]
        fi += 1  # MOT é 1-based
        tracks = tracker.update(dets, frame)
        for x1, y1, x2, y2, tid, conf, cls, _ in tracks:
            lines.append(f"{fi},{int(tid)},{x1:.2f},{y1:.2f},{x2 - x1:.2f},{y2 - y1:.2f},{conf:.4f},-1,-1,-1")
    cap.release()
    wall = time.time() - t0

    Path(out_txt).parent.mkdir(parents=True, exist_ok=True)
    Path(out_txt).write_text("\n".join(lines) + "\n")
    ids = {int(l.split(",")[1]) for l in lines}
    return {"tracker": tracker_name, "frames": fi, "wall_s": round(wall, 1),
            "fps_proc": round(fi / wall, 1), "n_tracks": len(ids), "n_boxes": len(lines)}
