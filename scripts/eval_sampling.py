"""Validação por amostragem (§7.7): MAE/viés de cada abordagem vs as contagens do autor
no vídeo principal, com IC 95% por bootstrap (10.000 reamostragens).

Referência humana: respostas_main.json (30 janelas × 5 instantes = 150 contagens, seed 42).
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
FPS_A = 5.0

answers = json.load(open("/mnt/c/Users/breno/TCC2/validacao_amostragem/respostas_main.json"))
POINTS = [(w["start_s"] + inst, c)
          for w in answers["windows"]
          for inst, c in zip([0.0, 7.5, 15.0, 22.5, 30.0], w["counts"]) if c is not None]


def mot_counts(path: Path) -> dict[int, int]:
    counts = defaultdict(set)
    for line in open(path):
        p = line.split(",")
        counts[int(p[0])].add(int(p[1]))
    return {f: len(s) for f, s in counts.items()}


def bootstrap_ci(errs: list[float], n: int = 10000) -> tuple[float, float]:
    rng = random.Random(42)
    maes = []
    for _ in range(n):
        sample = [abs(rng.choice(errs)) for _ in errs]
        maes.append(sum(sample) / len(sample))
    maes.sort()
    return maes[int(0.025 * n)], maes[int(0.975 * n)]


results = []

# --- Pipeline A (bytetrack E0 e pós-processado P4) ---
for name, path in [("A: bytetrack (E0)", D / "a2/a2_out/bytetrack/E0.txt"),
                   ("A: bytetrack +heurísticas (P4)", D / "a2/a2_out/bytetrack/E2/P4_stitch.txt"),
                   ("A: hybridsort (E0)", D / "a2/a2_out/hybridsort/E0.txt")]:
    if not path.exists():
        continue
    counts = mot_counts(path)
    errs = [counts.get(round(t * FPS_A) + 1, 0) - c for t, c in POINTS]
    lo, hi = bootstrap_ci(errs)
    results.append((name, sum(abs(e) for e in errs) / len(errs), sum(errs) / len(errs), lo, hi))

# --- Pipeline B (frames.jsonl @ 0,5 fps; frame mais próximo, tolerância 1s) ---
B_RUNS = {
    "B: Claude Haiku 4.5": D / "b2/b2_out/main_claude-haiku-4-5/frames.jsonl",
    "B: Claude Sonnet 5": D / "b2/b2_out/main_claude-sonnet-5/frames.jsonl",
    "B: Claude Opus 5": D / "b2/b2_out/main_claude-opus-5/frames.jsonl",
    "B: GPT-5.6 Luna": D / "b2/b2_out/main_6-luna/frames.jsonl",
    "B: GPT-5.6 Terra": D / "b2/b2_out/main_6-terra/frames.jsonl",
    "B: Gemma 4 26B-A4B": D / "b2/b2_out/main_gemma-4-26b-a4b/frames.jsonl",
    "B: Gemma 4 31B": D / "b2ext/b2_out/main_gemma-4-31b/frames.jsonl",
    "B: Grok 4.6": D / "b2ext/b2_out/main_6/frames.jsonl",
    "B: Qwen3-VL-8B self-hosted": D / "qwen/qwen_out/main/frames.jsonl",
    "B: GPT-5.6 Sol": D / "b2ext2/b2_out/main_6-sol/frames.jsonl",
    "B: GPT-6 Astra": D / "b2ext2/b2_out/main_gpt-6-astra/frames.jsonl",
}
for name, path in B_RUNS.items():
    if not path.exists():
        continue
    by_t = {}
    for line in open(path):
        r = json.loads(line)
        if r.get("ok"):
            by_t[r["t"]] = r["result"]["people_count"]
    errs = []
    for t, c in POINTS:
        near = min(by_t, key=lambda tt: abs(tt - t), default=None)
        if near is None or abs(near - t) > 1.01:
            continue
        errs.append(by_t[near] - c)
    if errs:
        lo, hi = bootstrap_ci(errs)
        results.append((name, sum(abs(e) for e in errs) / len(errs), sum(errs) / len(errs), lo, hi))

# --- B3 Pegasus (counts_at_instants por clipe; tolerância 5s) ---
b3 = json.load(open(D / "b3_results.json"))
by_t = {}
for cclip in b3["clips"]:
    if cclip["ok"]:
        for j, cnt in enumerate(cclip["result"]["counts_at_instants"][:6]):
            by_t[cclip["t_start"] + j * 10.0] = cnt
errs = []
for t, c in POINTS:
    near = min(by_t, key=lambda tt: abs(tt - t), default=None)
    if near is not None and abs(near - t) <= 5.01:
        errs.append(by_t[near] - c)
if errs:
    lo, hi = bootstrap_ci(errs)
    results.append((f"B3: Pegasus vídeo-nativo (n={len(errs)}, tol. 5s)",
                    sum(abs(e) for e in errs) / len(errs), sum(errs) / len(errs), lo, hi))

print(f"Validação por amostragem — vídeo principal ({len(POINTS)} contagens do autor, seed 42)")
print(f"{'abordagem':38s} {'MAE':>6s} {'viés':>7s} {'IC95% MAE':>15s}")
for name, mae, bias, lo, hi in sorted(results, key=lambda r: r[1]):
    print(f"{name:38s} {mae:6.3f} {bias:+7.3f}   [{lo:.3f}, {hi:.3f}]")

json.dump([{"approach": n, "mae": m, "bias": b, "ci95": [lo, hi]}
           for n, m, b, lo, hi in results],
          open(D / "sampling_validation_main.json", "w"), ensure_ascii=False, indent=1)
