"""Eixo E3 — re-identificação na mesma câmera como teto de custo.

Reassocia identidade de pessoa que reentra no campo de visão: extrai descritor de
aparência (OSNet) por trajetória e une trajetórias temporalmente disjuntas com
similaridade de cosseno acima do limiar. Recalcula o fluxo de visitantes únicos.

Contraste com stitch_tracks (E2): lá é proximidade espaço-temporal sem aparência
(barato); aqui é embedding dedicado (caro) — os dois extremos do espectro de custo.
"""
from __future__ import annotations

import numpy as np

from .postprocess import Track, parse_mot, dump_mot


def extract_track_embeddings(video: str, tracks: dict[int, Track],
                             reid_weights: str = "osnet_x1_0_msmt17.pt",
                             samples_per_track: int = 5, device: str = "cuda:0") -> dict[int, np.ndarray]:
    """Embedding médio de N crops amostrados uniformemente ao longo de cada trajetória."""
    import cv2
    from boxmot import ReIDModel

    model = ReIDModel.from_pretrained(reid_weights, device=device)

    # agenda: frame -> [(tid, box)]
    want: dict[int, list] = {}
    for t in tracks.values():
        fs = t.frames
        idx = np.linspace(0, len(fs) - 1, min(samples_per_track, len(fs))).astype(int)
        for i in idx:
            want.setdefault(fs[i], []).append((t.tid, t.boxes[fs[i]]))

    feats: dict[int, list] = {tid: [] for tid in tracks}
    cap = cv2.VideoCapture(video)
    fi = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        fi += 1  # MOT 1-based
        for tid, (x, y, w, h, _) in want.get(fi, []):
            x1, y1 = max(int(x), 0), max(int(y), 0)
            x2, y2 = min(int(x + w), frame.shape[1]), min(int(y + h), frame.shape[0])
            if x2 - x1 < 8 or y2 - y1 < 16:
                continue
            crop = frame[y1:y2, x1:x2]
            emb = model.get_features(np.array([[0, 0, crop.shape[1], crop.shape[0]]]), crop)
            feats[tid].append(np.asarray(emb).ravel())
    cap.release()

    out = {}
    for tid, fs_ in feats.items():
        if fs_:
            v = np.mean(fs_, axis=0)
            out[tid] = v / (np.linalg.norm(v) + 1e-8)
    return out


def merge_by_appearance(tracks: dict[int, Track], embs: dict[int, np.ndarray],
                        sim_threshold: float = 0.6) -> tuple[dict[int, Track], int]:
    """Une pares de trajetórias temporalmente DISJUNTAS com similaridade >= limiar (greedy)."""
    tids = [tid for tid in tracks if tid in embs]
    pairs = []
    for i, a in enumerate(tids):
        for b in tids[i + 1:]:
            ta, tb = tracks[a], tracks[b]
            if ta.frames[-1] < tb.frames[0] or tb.frames[-1] < ta.frames[0]:  # disjuntos
                sim = float(np.dot(embs[a], embs[b]))
                if sim >= sim_threshold:
                    pairs.append((sim, a, b))
    pairs.sort(reverse=True)

    merged_into: dict[int, int] = {}
    n = 0
    def root(x):
        while x in merged_into:
            x = merged_into[x]
        return x
    for sim, a, b in pairs:
        ra, rb = root(a), root(b)
        if ra == rb:
            continue
        ta, tb = tracks[ra], tracks[rb]
        if not (ta.frames[-1] < tb.frames[0] or tb.frames[-1] < ta.frames[0]):
            continue  # após merges anteriores deixaram de ser disjuntos
        ta.boxes.update(tb.boxes)
        merged_into[rb] = ra
        n += 1
    kept = {tid: t for tid, t in tracks.items() if tid not in merged_into}
    return kept, n


def run_reid(video: str, mot_in: str, mot_out: str,
             reid_weights: str = "osnet_x1_0_msmt17.pt", sim_threshold: float = 0.6) -> dict:
    tracks = parse_mot(mot_in)
    n_before = len(tracks)
    embs = extract_track_embeddings(video, tracks, reid_weights)
    tracks, n_merged = merge_by_appearance(tracks, embs, sim_threshold)
    dump_mot(tracks, mot_out)
    return {"tracks_before": n_before, "tracks_after": len(tracks),
            "reid_merges": n_merged, "unique_visitors": len(tracks)}
