"""Relatório consolidado das dimensões de avaliação (F4) — versão preliminar.

Cruza todos os artefatos medidos até aqui e emite markdown com as tabelas da monografia:
acurácia (ref), custo REAL por run, tempo/vazão, extrapolação mensal, complexidade.
Acurácia nos vídeos longos fica pendente da validação por amostragem do autor.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"

# ---------------- preços (verificados 23/08/2026; endpoint regional us-east-1) ----------------
PRICE_MTOK = {  # (input, output) US$/1M tokens
    "anthropic.claude-haiku-4-5": (1.10, 5.50),
    "anthropic.claude-sonnet-5": (2.20, 11.00),
    "anthropic.claude-opus-5": (5.50, 27.50),
    "openai.gpt-5.6-luna": (0.22, 1.32),
    "openai.gpt-5.6-terra": (2.20, 13.20),
    "google.gemma-4-26b-a4b": (0.13, 0.40),
    "google.gemma-4-31b": (0.14, 0.40),
    "us.xai.grok-4.6": (2.20, 6.60),
    "openai.gpt-5.6-sol": (4.40, 22.00),      # PROMO in-region (≥21/11/2026); cheio 5.50/33.00
    "us.openai.gpt-6-astra": (11.00, 55.00),  # in-region/Geo; sem promoção (lançado 08/09/2026)
}
# tarifa cheia (pós-promoção) para reportar as duas colunas de custo
PRICE_FULL_MTOK = {
    "openai.gpt-5.6-sol": (5.50, 33.00),
    "anthropic.claude-sonnet-5": (2.20, 11.00),  # promo virou permanente em 10/08/2026 — igual
}
GPU_HOUR = {"g6.xlarge": 0.8048, "g6.2xlarge": 0.9776}
PEGASUS_SEC = 0.00049
PEGASUS_OUT_MTOK = 7.50

MAIN_VIDEO_MIN = 36.6  # duração real do vídeo principal
MONTH_HOURS = 12 * 30  # extrapolação: loja aberta 12h/dia, 30 dias


def model_run_cost(model_id: str, tok_in: int, tok_out: int) -> float:
    pi, po = PRICE_MTOK[model_id]
    return tok_in / 1e6 * pi + tok_out / 1e6 * po


def gt_counts_and_occ():
    counts = defaultdict(set)
    zcfg = json.load(open(ROOT / "configs/zones/ref.json"))
    polys = {n: Polygon(p) for n, p in zcfg["zones"].items()}
    prio = zcfg["priority_order"]
    occ = defaultdict(float)
    for line in open(D / "gt_ref.txt"):
        p = line.split(",")
        f = int(p[0]); counts[f].add(int(p[1]))
        x, y, w, h = (float(v) for v in p[2:6])
        pt = Point(x + w / 2, y + h)
        zone = next((n for n in prio if polys[n].contains(pt)), "fora_de_zona")
        occ[zone] += 1 / 5.0
    return {f: len(s) for f, s in counts.items()}, dict(occ)


def load_eval(path: Path) -> list[dict]:
    return json.load(open(path)) if path.exists() else []


def main() -> None:
    gt_counts, gt_occ = gt_counts_and_occ()
    tot_gt_occ = sum(gt_occ.values())

    # ------- Pipeline B: junta avaliações do ref e summaries -------
    rows_b = []
    for d in ["b2", "b2ext", "b2ext2", "qwen"]:
        for r in load_eval(D / d / "b1_eval.json"):
            if not str(r["run"]).startswith(("ref", "qwen_out/ref")) and r.get("fps") and "ref" not in r["run"]:
                continue
            if "ref" not in r["run"]:
                continue
            occ_err = sum(abs(r["zone_person_seconds"].get(z, 0) - gt_occ.get(z, 0))
                          for z in set(gt_occ) | set(r["zone_person_seconds"]))
            rows_b.append({**r, "occ_err_pct": 100 * occ_err / tot_gt_occ})
    # custos do run MAIN por modelo (summaries)
    main_cost = {}
    for d, f in [("b2", "b2_summaries.json"), ("b2ext", "b2_summaries.json"), ("b2ext2", "b2_summaries.json")]:
        p = D / d / f
        if not p.exists():
            # summaries ficam no S3; usar os baixados se existirem
            continue
        for s in json.load(open(p)):
            if s.get("video_key") == "main" and "fatal_error" not in s:
                full = None
                if s["model_id"] in PRICE_FULL_MTOK:
                    pi, po = PRICE_FULL_MTOK[s["model_id"]]
                    full = s["input_tokens"] / 1e6 * pi + s["output_tokens"] / 1e6 * po
                main_cost[s["model_id"]] = {
                    "cost": model_run_cost(s["model_id"], s["input_tokens"], s["output_tokens"]),
                    "cost_full": full,
                    "wall_s": s["wall_total_s"], "fail": s["n_failures"]}
    qs = D / "qwen" / "qwen_summaries.json"
    if qs.exists():
        q = json.load(open(qs))
        hours = (q["ref"]["wall_total_s"] + q["main"]["wall_total_s"] + q["server_setup_s"]) / 3600
        frac_main = q["main"]["wall_total_s"] / (q["ref"]["wall_total_s"] + q["main"]["wall_total_s"])
        main_cost["local/Qwen3-VL-8B-FP8"] = {
            "cost": hours * GPU_HOUR["g6.2xlarge"] * frac_main,
            "wall_s": q["main"]["wall_total_s"], "fail": q["main"]["n_failures"]}

    # ------- Pegasus B3 -------
    b3 = json.load(open(D / "b3_results.json")) if (D / "b3_results.json").exists() else None
    pegasus_cost = None
    if b3:
        oks = [c for c in b3["clips"] if c["ok"]]
        pegasus_cost = {"cost": MAIN_VIDEO_MIN * 60 * PEGASUS_SEC,  # + saída (pequena)
                        "wall_s": b3["wall_total_s"], "clips_ok": f"{len(oks)}/{b3['n_clips']}",
                        "interactions": sum(len(c["result"]["interactions"]) for c in oks)}

    # ------- Pipeline A: triagem + eixos -------
    screening = json.load(open(ROOT / "runs/screening_eval/summary.json")) \
        if (ROOT / "runs/screening_eval/summary.json").exists() else {}

    # ------- monta o markdown -------
    L = ["# Resultados preliminares — tabelas consolidadas",
         "", f"_Gerado automaticamente; preços de 23/08/2026 (endpoint regional us-east-1). "
         f"Acurácia nos vídeos longos pendente da validação por amostragem._", ""]

    L += ["## 1. Pipeline A — triagem de rastreadores (vídeo de referência, GT denso)", "",
          "| tracker | MOTA | IDF1 | HOTA | IDSW | tempo (s) |", "|---|---|---|---|---|---|"]
    wall_a = {"bytetrack": 14.5, "ocsort": 14.6, "botsort": 48.0, "deepocsort": 48.1,
              "strongsort": 86.4, "boosttrack": 58.3, "hybridsort": 69.0}
    for trk, m in sorted(screening.items(), key=lambda kv: -(kv[1]["MOTA"] + kv[1]["IDF1"])):
        L.append(f"| {trk} | {m['MOTA']:.2f} | {m['IDF1']:.2f} | {m['HOTA']:.2f} | {m['IDSW']} | {wall_a.get(trk,'—')} |")

    L += ["", "## 2. Pipeline B — acurácia no vídeo de referência (0,5 fps)", "",
          "| modelo | MAE contagem | viés | erro ocupação zona | falhas schema |",
          "|---|---|---|---|---|"]
    def label(r):
        run = r["run"]
        return {"ref_claude-haiku-4-5": "Claude Haiku 4.5", "ref_claude-sonnet-5": "Claude Sonnet 5",
                "ref_claude-opus-5": "Claude Opus 5", "ref_6-luna": "GPT-5.6 Luna",
                "ref_6-terra": "GPT-5.6 Terra", "ref_gemma-4-26b-a4b": "Gemma 4 26B-A4B",
                "ref_gemma-4-31b": "Gemma 4 31B", "ref_6": "Grok 4.6", "ref": "Qwen3-VL-8B (self-hosted)",
                "ref_6-sol": "GPT-5.6 Sol", "ref_gpt-6-astra": "GPT-6 Astra"}.get(run, run)
    for r in sorted(rows_b, key=lambda r: r["mae"]):
        L.append(f"| {label(r)} | {r['mae']:.3f} | {r['bias']:+.3f} | {r['occ_err_pct']:.0f}% | {r['failures']} |")

    L += ["", "## 3. Custo e tempo REAIS — vídeo principal (36,6 min) por abordagem", "",
          "| abordagem | custo do vídeo (US$) | tempo (s) | US$/h de vídeo | US$/mês (360h) |",
          "|---|---|---|---|---|"]
    # Pipeline A: detecção main 160,6s + tracking bytetrack 94,4s na g6.xlarge
    a_secs = 160.6 + 94.4
    a_cost = a_secs / 3600 * GPU_HOUR["g6.xlarge"]
    per_h_a = a_cost / (MAIN_VIDEO_MIN / 60)
    L.append(f"| Pipeline A (YOLO26m+bytetrack, GPU) | {a_cost:.3f} | {a_secs:.0f} | {per_h_a:.3f} | {per_h_a*MONTH_HOURS:.0f} |")
    a3 = 160.6 + 94.4 + 99.3  # + ReID E3
    a3_cost = a3 / 3600 * GPU_HOUR["g6.xlarge"]
    per_h_a3 = a3_cost / (MAIN_VIDEO_MIN / 60)
    L.append(f"| Pipeline A + ReID (teto) | {a3_cost:.3f} | {a3:.0f} | {per_h_a3:.3f} | {per_h_a3*MONTH_HOURS:.0f} |")
    name_map = {"anthropic.claude-haiku-4-5": "B: Claude Haiku 4.5", "anthropic.claude-sonnet-5": "B: Claude Sonnet 5",
                "anthropic.claude-opus-5": "B: Claude Opus 5", "openai.gpt-5.6-luna": "B: GPT-5.6 Luna",
                "openai.gpt-5.6-terra": "B: GPT-5.6 Terra", "google.gemma-4-26b-a4b": "B: Gemma 4 26B-A4B",
                "google.gemma-4-31b": "B: Gemma 4 31B", "us.xai.grok-4.6": "B: Grok 4.6",
                "local/Qwen3-VL-8B-FP8": "B: Qwen3-VL-8B self-hosted (GPU)",
                "openai.gpt-5.6-sol": "B: GPT-5.6 Sol", "us.openai.gpt-6-astra": "B: GPT-6 Astra"}
    for mid, c in sorted(main_cost.items(), key=lambda kv: kv[1]["cost"]):
        per_h = c["cost"] / (MAIN_VIDEO_MIN / 60)
        extra = ""
        if c.get("cost_full") and abs(c["cost_full"] - c["cost"]) > 1e-6:
            ph_full = c["cost_full"] / (MAIN_VIDEO_MIN / 60)
            extra = f" (tarifa cheia: {c['cost_full']:.3f} / {ph_full*MONTH_HOURS:.0f}/mês)"
        L.append(f"| {name_map.get(mid, mid)}{extra} | {c['cost']:.3f} | {c['wall_s']:.0f} | {per_h:.3f} | {per_h*MONTH_HOURS:.0f} |")
    if pegasus_cost:
        per_h = pegasus_cost["cost"] / (MAIN_VIDEO_MIN / 60)
        L.append(f"| B3: Pegasus 1.2 (vídeo-nativo) | {pegasus_cost['cost']:.3f} | {pegasus_cost['wall_s']:.0f} | {per_h:.3f} | {per_h*MONTH_HOURS:.0f} |")

    L += ["", "_Extrapolação: 12h de operação/dia × 30 dias = 360h de vídeo/mês por loja. "
          "Custo do Pipeline B a 0,5 fps; taxas maiores escalam ~linearmente. "
          "Pipeline A assume instância dedicada apenas durante o processamento (batch)._", ""]

    if b3:
        oks = [c for c in b3["clips"] if c["ok"]]
        L += ["## 4. Eixo B3 — vídeo-nativo (Pegasus 1.2, 37 clipes de 60s)", "",
              f"- Clipes processados: {len(oks)}/{b3['n_clips']}; tempo total {b3['wall_total_s']:.0f}s",
              f"- Interações pessoa-produto detectadas: {sum(len(c['result']['interactions']) for c in oks)} "
              f"(validação contra eventos BORIS pendente)",
              f"- Únicos por clipe (soma, com dupla contagem entre clipes): "
              f"{sum(c['result']['unique_people'] for c in oks)} — limitação do fatiamento a declarar", ""]

    L += ["## 5. Complexidade de implementação (contagens objetivas até 23/08)", "",
          "| indicador | Pipeline A | Pipeline B (gerenciado) | B self-hosted |", "|---|---|---|---|",
          "| falhas de infra/ambiente no projeto | 4 (ffmpeg/DLAMI, CVAT MOT ×2, API boxmot) | 1 (CLI ausente em AMI) | 2 (ninja/vLLM, capacidade GPU) |",
          "| falhas de schema/modelo | — | 91 frames (só Sonnet 5; limitação documentada) | 0 |",
          "| dependências de runtime | torch, ultralytics, boxmot, TrackEval (numpy<1.24!) | 2 SDKs HTTP | vllm + torch + GPU |",
          "| hardware dedicado | GPU | nenhum | GPU |", ""]

    sv = D / "sampling_validation_main.json"
    if sv.exists():
        rows = json.load(open(sv))
        L += ["## 6. Validação por amostragem — vídeo principal (150 contagens do autor, seed 42, critério inclusivo v2)", "",
              "| abordagem | MAE | viés | IC95% do MAE |", "|---|---|---|---|"]
        for r in sorted(rows, key=lambda r: r["mae"]):
            L.append(f"| {r['approach']} | {r['mae']:.3f} | {r['bias']:+.3f} | [{r['ci95'][0]:.3f}, {r['ci95'][1]:.3f}] |")
        L += ["", "_Sensibilidade à definição (v1 estrito × v2 inclusivo): 96/150 instantes mudaram (+143 pessoas parciais, +41%); "
              "o ranking muda substancialmente entre critérios — ver DECISOES.md D16._", ""]

    out = ROOT / "docs" / "RESULTADOS_PRELIMINARES.md"
    out.write_text("\n".join(L), encoding="utf-8")
    Path("/mnt/c/Users/breno/TCC2/RESULTADOS_PRELIMINARES.md").write_text("\n".join(L), encoding="utf-8")
    print(f"gerado: {out} (+ cópia no TCC2)")


if __name__ == "__main__":
    main()
