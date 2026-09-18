"""Avaliação dos eventos IHO (§3.8): precisão/revocação de pegar/devolver com tolerância
temporal (±5s) e correspondência de zona, contra o gabarito BORIS do vídeo de referência;
estados de 'examinar' avaliados por sobreposição temporal (IoU por zona).

Candidatos: modelos B2 no ref (ações por frame @0,5fps → eventos deduplicados)
e Pegasus vídeo-nativo no ref (interações por clipe).
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
TOL = 5.0  # tolerância temporal (s) — pré-registrada na metodologia

# ---------- gabarito ----------
gt_points, gt_states = [], defaultdict(list)
for row in csv.DictReader(open(D / "boris_eventos_ref.csv")):
    if row["type"] == "examinar_produto":
        gt_states[row["zone"]].append((float(row["t_start"]), float(row["t_end"])))
    else:
        gt_points.append({"t": float(row["t_start"]), "type": row["type"], "zone": row["zone"]})

ACTION_MAP = {"pegando_produto": "pegar_produto", "devolvendo_produto": "devolver_produto"}


def frames_to_events(frames_jsonl: Path) -> tuple[list[dict], dict[str, list]]:
    """Ações por frame → eventos points deduplicados + intervalos de examinar por zona."""
    raw_points, exam_frames = [], defaultdict(list)
    dt = None
    prev_t = None
    for line in open(frames_jsonl):
        r = json.loads(line)
        if not r.get("ok"):
            continue
        if prev_t is not None and dt is None:
            dt = r["t"] - prev_t
        prev_t = r["t"]
        for person in r["result"]["people"]:
            act = person["action"]
            if act in ACTION_MAP:
                raw_points.append({"t": r["t"], "type": ACTION_MAP[act], "zone": person["zone"]})
            if act == "examinando_produto" or person.get("interacting_with_product"):
                exam_frames[person["zone"]].append(r["t"])
    dt = dt or 2.0
    # dedup: mesmo tipo+zona em frames consecutivos = 1 evento
    raw_points.sort(key=lambda e: (e["type"], e["zone"], e["t"]))
    points, last = [], {}
    for e in raw_points:
        k = (e["type"], e["zone"])
        if k in last and e["t"] - last[k] <= dt + 0.1:
            last[k] = e["t"]
            continue
        last[k] = e["t"]
        points.append(e)
    # intervalos de examinar: frames consecutivos por zona → segmentos
    states = defaultdict(list)
    for zone, ts in exam_frames.items():
        ts = sorted(set(ts))
        start = prev = ts[0]
        for t in ts[1:]:
            if t - prev <= dt + 0.1:
                prev = t
                continue
            states[zone].append((start, prev + dt))
            start = prev = t
        states[zone].append((start, prev + dt))
    return points, dict(states)


def pegasus_events(b3_json: Path) -> list[dict]:
    d = json.load(open(b3_json))
    out = []
    for clip in d["clips"]:
        if not clip["ok"]:
            continue
        for it in clip["result"]["interactions"]:
            act = ACTION_MAP.get(it["action"])
            if act:
                out.append({"t": clip["t_start"] + it["t_seconds"], "type": act, "zone": None})
    return out


def pr_match(pred: list[dict], zone_match: bool) -> tuple[float, float, int, int]:
    used = set()
    tp = 0
    for p in sorted(pred, key=lambda e: e["t"]):
        best, best_d = None, TOL + 1
        for i, g in enumerate(gt_points):
            if i in used or g["type"] != p["type"]:
                continue
            if zone_match and p.get("zone") is not None and p["zone"] != g["zone"]:
                continue
            dist = abs(p["t"] - g["t"])
            if dist <= TOL and dist < best_d:
                best, best_d = i, dist
        if best is not None:
            used.add(best)
            tp += 1
    prec = tp / len(pred) if pred else 0.0
    rec = tp / len(gt_points) if gt_points else 0.0
    return prec, rec, tp, len(pred)


def state_iou(states: dict[str, list]) -> float:
    def merge(iv):
        iv = sorted(iv)
        out = []
        for a, b in iv:
            if out and a <= out[-1][1]:
                out[-1][1] = max(out[-1][1], b)
            else:
                out.append([a, b])
        return out
    inter = union = 0.0
    zones = set(gt_states) | set(states)
    for z in zones:
        g, p = merge(gt_states.get(z, [])), merge(states.get(z, []))
        gi = sum(b - a for a, b in g)
        pi = sum(b - a for a, b in p)
        ov = 0.0
        for ga, gb in g:
            for pa, pb in p:
                ov += max(0.0, min(gb, pb) - max(ga, pa))
        inter += ov
        union += gi + pi - ov
    return inter / union if union else 0.0


RUNS = {
    "Claude Haiku 4.5": D / "b2/b2_out/ref_claude-haiku-4-5/frames.jsonl",
    "Claude Sonnet 5": D / "b2/b2_out/ref_claude-sonnet-5/frames.jsonl",
    "Claude Opus 5": D / "b2/b2_out/ref_claude-opus-5/frames.jsonl",
    "GPT-5.6 Luna": D / "b2/b2_out/ref_6-luna/frames.jsonl",
    "GPT-5.6 Terra": D / "b2/b2_out/ref_6-terra/frames.jsonl",
    "Gemma 4 26B-A4B": D / "b2/b2_out/ref_gemma-4-26b-a4b/frames.jsonl",
    "Gemma 4 31B": D / "b2ext/b2_out/ref_gemma-4-31b/frames.jsonl",
    "Grok 4.6": D / "b2ext/b2_out/ref_6/frames.jsonl",
    "Qwen3-VL-8B self-hosted": D / "qwen/qwen_out/ref/frames.jsonl",
    "GPT-5.6 Sol": D / "b2ext2/b2_out/ref_6-sol/frames.jsonl",
    "GPT-6 Astra": D / "b2ext2/b2_out/ref_gpt-6-astra/frames.jsonl",
}

print(f"Gabarito BORIS: {len(gt_points)} points, {sum(len(v) for v in gt_states.values())} estados")
print(f"\n{'modelo':28s} {'P(zona)':>8s} {'R(zona)':>8s} {'P(tempo)':>9s} {'R(tempo)':>9s} {'n_pred':>6s} {'IoU exam':>9s}")
results = []
for name, path in RUNS.items():
    if not path.exists():
        continue
    points, states = frames_to_events(path)
    pz, rz, *_ = pr_match(points, zone_match=True)
    pt_, rt_, _, npred = pr_match(points, zone_match=False)
    iou = state_iou(states)
    results.append({"model": name, "prec_zone": pz, "rec_zone": rz,
                    "prec_time": pt_, "rec_time": rt_, "n_pred": npred, "exam_iou": iou})
    print(f"{name:28s} {pz:8.2f} {rz:8.2f} {pt_:9.2f} {rt_:9.2f} {npred:6d} {iou:9.2f}")

pg = D / "b3ref_results.json"
if pg.exists():
    ev = pegasus_events(pg)
    pt_, rt_, _, npred = pr_match(ev, zone_match=False)
    results.append({"model": "Pegasus 1.2 (vídeo-nativo)", "prec_time": pt_, "rec_time": rt_,
                    "n_pred": npred, "exam_iou": None})
    print(f"{'Pegasus 1.2 (vídeo-nativo)':28s} {'—':>8s} {'—':>8s} {pt_:9.2f} {rt_:9.2f} {npred:6d} {'—':>9s}")

json.dump(results, open(D / "iho_eval_ref.json", "w"), ensure_ascii=False, indent=1)
print(f"\nsalvo: {D / 'iho_eval_ref.json'}")
