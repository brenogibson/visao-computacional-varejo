"""Avaliação do eixo B1: MAE/viés de contagem por frame dos MLLMs vs ground truth,
por taxa de amostragem — decide a taxa vencedora pelo critério pré-registrado
(menor taxa cujo MAE não piora >10% vs a taxa acima).

Local (D13: análise estatística). Uso:
  python scripts/eval_b1.py --gt data/gt_ref.txt --b1-dir data/b1/b1_out
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

GT_FPS = 5.0


def gt_counts(gt_txt: Path) -> dict[int, int]:
    counts: dict[int, set] = defaultdict(set)
    for line in open(gt_txt):
        p = line.split(",")
        counts[int(p[0])].add(int(p[1]))
    return {f: len(s) for f, s in counts.items()}


def eval_run(frames_jsonl: Path, gt: dict[int, int]) -> dict:
    errs, pairs = [], 0
    zone_occ: dict[str, float] = defaultdict(float)
    n_fail = 0
    dt = None
    recs = [json.loads(l) for l in open(frames_jsonl)]
    if len(recs) > 1:
        dt = recs[1]["t"] - recs[0]["t"]
    for rec in recs:
        if not rec.get("ok"):
            n_fail += 1
            continue
        gt_frame = round(rec["t"] * GT_FPS) + 1  # MOT 1-based
        if gt_frame not in gt:
            gt_c = 0
        else:
            gt_c = gt[gt_frame]
        pred_c = rec["result"]["people_count"]
        errs.append(pred_c - gt_c)
        pairs += 1
        for person in rec["result"]["people"]:
            zone_occ[person["zone"]] += dt or 1.0
    mae = sum(abs(e) for e in errs) / max(pairs, 1)
    bias = sum(errs) / max(pairs, 1)
    return {"pairs": pairs, "failures": n_fail, "mae": round(mae, 3),
            "bias": round(bias, 3), "zone_person_seconds": {k: round(v, 1) for k, v in sorted(zone_occ.items())}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", type=Path, required=True)
    ap.add_argument("--b1-dir", type=Path, required=True)
    args = ap.parse_args()

    gt = gt_counts(args.gt)
    rows = []
    for run_dir in sorted(args.b1_dir.iterdir()):
        fj = run_dir / "frames.jsonl"
        if not fj.exists():
            continue
        summary = json.loads((run_dir / "run_summary.json").read_text())
        ev = eval_run(fj, gt)
        rows.append({"run": run_dir.name, "model": summary["model_id"], "fps": summary["fps"],
                     "wall_s": summary["wall_total_s"],
                     "input_tokens": summary["input_tokens"], "output_tokens": summary["output_tokens"],
                     "reasoning_tokens": summary.get("reasoning_tokens", 0), **ev})

    print(f"{'run':28s} {'fps':>4s} {'MAE':>6s} {'viés':>6s} {'falhas':>6s} {'tok_in':>9s} {'tok_out':>8s} {'wall_s':>7s}")
    for r in sorted(rows, key=lambda r: (r["model"], r["fps"])):
        print(f"{r['run']:28s} {r['fps']:4.1f} {r['mae']:6.3f} {r['bias']:+6.3f} {r['failures']:6d} "
              f"{r['input_tokens']:9d} {r['output_tokens']:8d} {r['wall_s']:7.1f}")
    out = args.b1_dir.parent / "b1_eval.json"
    json.dump(rows, open(out, "w"), indent=1, ensure_ascii=False)
    print(f"\nsalvo: {out}")


if __name__ == "__main__":
    main()
