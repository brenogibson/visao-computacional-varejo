"""Eixo E2 — heurísticas de pós-processamento de trajetórias (contribuição central do TCC).

Quatro heurísticas de baixo custo, habilitáveis de forma independente, aplicadas sobre a
saída MOT do tracker (nunca sobre a detecção — métricas independentes de identidade
não mudam). Cada uma loga o nº de trajetórias afetadas (exigência da seção 3.4).

Ablação incremental (D02): P0 = tracker puro; P1 = +min_len; P2 = +min_conf;
P3 = +interpolação de lacunas; P4 = +costura espaço-temporal.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class Track:
    tid: int
    # frame -> (x, y, w, h, conf)
    boxes: dict[int, tuple[float, float, float, float, float]] = field(default_factory=dict)

    @property
    def frames(self) -> list[int]:
        return sorted(self.boxes)

    @property
    def mean_conf(self) -> float:
        return sum(b[4] for b in self.boxes.values()) / len(self.boxes)


def parse_mot(path: str) -> dict[int, Track]:
    tracks: dict[int, Track] = {}
    for line in open(path):
        p = line.strip().split(",")
        if len(p) < 7:
            continue
        f, tid = int(p[0]), int(p[1])
        x, y, w, h, conf = (float(v) for v in p[2:7])
        tracks.setdefault(tid, Track(tid)).boxes[f] = (x, y, w, h, conf)
    return tracks


def dump_mot(tracks: dict[int, Track], path: str) -> None:
    lines = []
    for t in tracks.values():
        for f in t.frames:
            x, y, w, h, conf = t.boxes[f]
            lines.append(f"{f},{t.tid},{x:.2f},{y:.2f},{w:.2f},{h:.2f},{conf:.4f},-1,-1,-1")
    lines.sort(key=lambda l: (int(l.split(",")[0]), int(l.split(",")[1])))
    open(path, "w").write("\n".join(lines) + "\n")


def filter_min_length(tracks: dict[int, Track], min_len: int = 5) -> tuple[dict[int, Track], int]:
    """Descarta trajetórias muito curtas (falso positivo / perda de rastreamento)."""
    kept = {tid: t for tid, t in tracks.items() if len(t.boxes) >= min_len}
    return kept, len(tracks) - len(kept)


def filter_min_conf(tracks: dict[int, Track], min_conf: float = 0.4) -> tuple[dict[int, Track], int]:
    """Descarta trajetórias com confiança média baixa."""
    kept = {tid: t for tid, t in tracks.items() if t.mean_conf >= min_conf}
    return kept, len(tracks) - len(kept)


def interpolate_gaps(tracks: dict[int, Track], max_gap: int = 10) -> tuple[dict[int, Track], int]:
    """Preenche lacunas curtas de detecção por interpolação linear."""
    n_filled = 0
    for t in tracks.values():
        fs = t.frames
        filled_any = False
        for a, b in zip(fs, fs[1:]):
            gap = b - a
            if 1 < gap <= max_gap:
                xa, ya, wa, ha, ca = t.boxes[a]
                xb, yb, wb, hb, cb = t.boxes[b]
                for k in range(1, gap):
                    r = k / gap
                    t.boxes[a + k] = (xa + (xb - xa) * r, ya + (yb - ya) * r,
                                      wa + (wb - wa) * r, ha + (hb - ha) * r,
                                      min(ca, cb))
                filled_any = True
        n_filled += filled_any
    return tracks, n_filled


def stitch_tracks(tracks: dict[int, Track], max_gap: int = 25,
                  max_dist: float = 150.0) -> tuple[dict[int, Track], int]:
    """Costura trajetórias fragmentadas por proximidade espaço-temporal (SEM embeddings).

    Une track B a track A quando B começa logo após o fim de A (gap <= max_gap frames)
    e o centro da 1ª caixa de B está a menos de max_dist px do centro da última de A.
    Greedy por menor distância; cada fragmento é usado no máximo uma vez.
    """
    def center(box):
        x, y, w, h, _ = box
        return (x + w / 2, y + h / 2)

    order = sorted(tracks.values(), key=lambda t: t.frames[0])
    merged_into: dict[int, int] = {}
    n_stitch = 0
    for b in order:
        if b.tid in merged_into:
            continue
        best, best_d = None, max_dist
        for a in order:
            if a.tid == b.tid or a.tid in merged_into:
                continue
            end_a, start_b = a.frames[-1], b.frames[0]
            if not (0 < start_b - end_a <= max_gap):
                continue
            ca, cb = center(a.boxes[end_a]), center(b.boxes[start_b])
            d = ((ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2) ** 0.5
            if d < best_d:
                best, best_d = a, d
        if best is not None:
            best.boxes.update(b.boxes)
            merged_into[b.tid] = best.tid
            n_stitch += 1
    kept = {tid: t for tid, t in tracks.items() if tid not in merged_into}
    return kept, n_stitch


STAGES = ["P0_baseline", "P1_minlen", "P2_minconf", "P3_interp", "P4_stitch"]


def run_incremental(mot_in: str, out_dir: str) -> list[dict]:
    """Aplica a ablação incremental; grava um MOT por estágio e retorna os logs."""
    from pathlib import Path
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    logs = []
    tracks = parse_mot(mot_in)
    dump_mot(tracks, f"{out_dir}/P0_baseline.txt")
    logs.append({"stage": "P0_baseline", "n_tracks": len(tracks)})

    tracks, n = filter_min_length(tracks)
    dump_mot(tracks, f"{out_dir}/P1_minlen.txt")
    logs.append({"stage": "P1_minlen", "n_tracks": len(tracks), "discarded": n})

    tracks, n = filter_min_conf(tracks)
    dump_mot(tracks, f"{out_dir}/P2_minconf.txt")
    logs.append({"stage": "P2_minconf", "n_tracks": len(tracks), "discarded": n})

    tracks, n = interpolate_gaps(tracks)
    dump_mot(tracks, f"{out_dir}/P3_interp.txt")
    logs.append({"stage": "P3_interp", "n_tracks": len(tracks), "tracks_filled": n})

    tracks, n = stitch_tracks(tracks)
    dump_mot(tracks, f"{out_dir}/P4_stitch.txt")
    logs.append({"stage": "P4_stitch", "n_tracks": len(tracks), "stitched": n})
    return logs
