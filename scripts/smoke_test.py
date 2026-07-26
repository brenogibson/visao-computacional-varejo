"""Smoke test da Fase 0: YOLO26 + BoxMOT + zonas aprovadas, ponta a ponta em 30s de vídeo.
Critério de conclusão da F0: roda sem erro e grava métricas no schema canônico + runlog."""
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ultralytics import YOLO
from boxmot.trackers.registry import create_tracker
from shapely.geometry import Point, Polygon

from retailcv import runlog
from retailcv.schema import (Action, FrameObservation, PersonObservation,
                             VideoMetrics, ZoneDwell)
from retailcv.video import probe

VIDEO = Path(__file__).resolve().parents[1] / "data" / "ref_smoke_5fps.mp4"
ZONES_FILE = Path(__file__).resolve().parents[1] / "configs" / "zones" / "ref.json"
FPS = 5.0

zcfg = json.loads(ZONES_FILE.read_text())
polys = {n: Polygon(pts) for n, pts in zcfg["zones"].items()}
priority = zcfg["priority_order"]


def zone_of(x_center: float, y_bottom: float) -> str:
    p = Point(x_center, y_bottom)
    for name in priority:
        if polys[name].contains(p):
            return name
    return "fora_de_zona"


def main() -> None:
    t0 = time.time()
    info = probe(VIDEO)
    run_dir = runlog.new_run("smoke", seed=42, out_root=Path(__file__).resolve().parents[1] / "runs")

    model = YOLO("yolo26m.pt")
    tracker = create_tracker("bytetrack", reid_weights=None, device="cuda:0", half=True)

    cap = cv2.VideoCapture(str(VIDEO))
    frames_out: list[FrameObservation] = []
    dwell = defaultdict(float)
    ids_by_zone = defaultdict(set)
    frame_i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        r = model.predict(frame, classes=[0], conf=0.25, verbose=False)[0]
        dets = np.hstack([
            r.boxes.xyxy.cpu().numpy(),
            r.boxes.conf.cpu().numpy()[:, None],
            r.boxes.cls.cpu().numpy()[:, None],
        ]).astype(np.float32) if len(r.boxes) else np.empty((0, 6), dtype=np.float32)
        tracks = tracker.update(dets, frame)  # (M,8): x1,y1,x2,y2,id,conf,cls,det_ind
        people = []
        for x1, y1, x2, y2, tid, conf, cls, _ in tracks:
            zn = zone_of((x1 + x2) / 2, y2)
            people.append(PersonObservation(zone=zn, person_id=f"p{int(tid):03d}",
                                            bbox=(float(x1), float(y1), float(x2), float(y2))))
            dwell[zn] += 1 / FPS
            ids_by_zone[zn].add(int(tid))
        frames_out.append(FrameObservation(t_seconds=frame_i / FPS,
                                           people_count=len(people), people=people))
        frame_i += 1
    cap.release()

    metrics = VideoMetrics(
        run_id=run_dir.name, video_id="ref_smoke", video_sha256=info.sha256,
        pipeline="A", config_ref="smoke",
        frames=frames_out,
        zone_dwell=[ZoneDwell(zone=z, person_seconds=round(s, 1),
                              unique_visitors=len(ids_by_zone[z])) for z, s in sorted(dwell.items())],
        interaction_events=[],
        total_unique_visitors=len(set().union(*ids_by_zone.values())) if ids_by_zone else 0,
    )
    (run_dir / "metrics.json").write_text(metrics.model_dump_json(indent=1))
    wall = time.time() - t0
    runlog.finalize_run(run_dir, cost_usd=0.0, wall_time_s=wall)

    print(f"frames processados: {frame_i} | wall: {wall:.1f}s | "
          f"throughput: {frame_i / wall:.1f} fps de processamento (vídeo é 5 fps => {frame_i/wall/FPS:.1f}x tempo real)")
    print(f"visitantes únicos (IDs de tracking): {metrics.total_unique_visitors}")
    for zd in metrics.zone_dwell:
        print(f"  {zd.zone:20s} {zd.person_seconds:7.1f} pessoa-s | {zd.unique_visitors} ids")
    print(f"artefatos: {run_dir}/")


if __name__ == "__main__":
    main()
