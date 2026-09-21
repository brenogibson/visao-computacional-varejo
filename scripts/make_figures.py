"""Gera as figuras da monografia a partir dos artefatos medidos (reprodutível).

Saídas (PNG 300 dpi) em --out (padrão: docs/figuras/):
  zonas_{ref,main}_poligonos.png   polígonos das zonas (sem quadros de vídeo — LGPD)
  fig_custo_vs_mae.png             custo mensal projetado (log) x MAE no vídeo principal
  fig_mae_ref_vs_main.png          MAE por modelo nos dois vídeos (dumbbell)
Paleta categórica validada (dataviz): #2a78d6 / #eb6834 / #1baf7a; sequencial azul para o dumbbell.
"""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon as P

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "figuras"
OUT.mkdir(parents=True, exist_ok=True)
INK2, MUTED, GRID, SURF = "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
C_A, C_B, C_V = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})

def zonas():
    COL = {"entrada": "#2ecc71", "corredor_esquerdo": "#3498db", "corredor_central": "#e91e8c",
           "mesa_central": "#e74c3c", "corredor_direito": "#f39c12", "caixa": "#9b59b6"}
    NUDGE = {("ref", "mesa_central"): (0, 110), ("ref", "corredor_central"): (60, -40)}
    for key in ["ref", "main"]:
        z = json.load(open(ROOT / f"configs/zones/{key}.json"))
        fig, ax = plt.subplots(figsize=(9.6, 5.4), dpi=200); ax.set_facecolor("#f4f4f4")
        for name in reversed(z["priority_order"]):
            pts = z["zones"][name]
            ax.add_patch(P(pts, closed=True, facecolor=COL[name], alpha=.45, edgecolor=COL[name], lw=2.5))
            cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
            dx, dy = NUDGE.get((key, name), (0, 0))
            ax.text(cx + dx, min(cy + dy, 1030), name.replace("_", "\n"), ha="center", va="center", fontsize=15,
                    fontweight="bold", color="#222", bbox=dict(facecolor="white", alpha=.75, pad=3, lw=0))
        ax.set_xlim(0, 1920); ax.set_ylim(1080, 0)
        ax.set_xticks([0, 480, 960, 1440, 1920]); ax.set_yticks([0, 270, 540, 810, 1080]); ax.tick_params(labelsize=12); ax.grid(alpha=.3)
        ax.set_xlabel("x (pixels)", fontsize=12); ax.set_ylabel("y (pixels)", fontsize=12)
        fig.tight_layout(); fig.savefig(OUT / f"zonas_{key}_poligonos.png"); plt.close(fig)

def dados():
    cost = {}
    for l in open(ROOT / "docs/RESULTADOS_PRELIMINARES.md"):
        m = re.match(r"\| (.+?) \| ([\d.]+) \| \d+ \| [\d.]+ \| (\d+) \|", l)
        if m: cost[m.group(1)] = float(m.group(3))
    samp = {r["approach"]: r for r in json.load(open(ROOT / "data/sampling_validation_main.json"))}
    MAP = [("Pipeline A (ByteTrack)", "Pipeline A (YOLO26m+bytetrack, GPU)", "A: bytetrack (E0)", "A", False),
           ("Gemma 4 26B", "B: Gemma 4 26B-A4B", "B: Gemma 4 26B-A4B", "B", False), ("Gemma 4 31B", "B: Gemma 4 31B", "B: Gemma 4 31B", "B", False),
           ("Qwen3-VL-8B", "B: Qwen3-VL-8B self-hosted (GPU)", "B: Qwen3-VL-8B self-hosted", "B", True),
           ("GPT-5.6 Luna", "B: GPT-5.6 Luna", "B: GPT-5.6 Luna", "B", False), ("Claude Haiku 4.5", "B: Claude Haiku 4.5", "B: Claude Haiku 4.5", "B", False),
           ("Grok 4.6", "B: Grok 4.6", "B: Grok 4.6", "B", False), ("GPT-5.6 Terra", "B: GPT-5.6 Terra", "B: GPT-5.6 Terra", "B", False),
           ("Claude Sonnet 5", "B: Claude Sonnet 5", "B: Claude Sonnet 5", "B", False),
           ("GPT-5.6 Sol", "B: GPT-5.6 Sol (tarifa cheia: 39.833 / 23508/mês)", "B: GPT-5.6 Sol", "B", False),
           ("Claude Opus 5", "B: Claude Opus 5", "B: Claude Opus 5", "B", False), ("GPT-6 Astra", "B: GPT-6 Astra", "B: GPT-6 Astra", "B", False)]
    peg = [k for k in samp if k.startswith("B3: Pegasus")][0]
    pts = [(lab, cost[ck], samp[sk]["mae"], samp[sk]["ci95"], g, sh) for lab, ck, sk, g, sh in MAP]
    pts.append(("Pegasus 1.2 (vídeo nativo)", 635.0, samp[peg]["mae"], samp[peg]["ci95"], "V", False))
    ref = {}
    for d in ["b2", "b2ext", "b2ext2", "qwen"]:
        for r in json.load(open(ROOT / f"data/{d}/b1_eval.json")):
            if "ref" in r["run"]: ref[r["run"]] = r["mae"]
    REF_KEY = {"Claude Haiku 4.5": "ref_claude-haiku-4-5", "Claude Sonnet 5": "ref_claude-sonnet-5", "Claude Opus 5": "ref_claude-opus-5",
               "GPT-5.6 Luna": "ref_6-luna", "GPT-5.6 Terra": "ref_6-terra", "Gemma 4 26B": "ref_gemma-4-26b-a4b", "Gemma 4 31B": "ref_gemma-4-31b",
               "Grok 4.6": "ref_6", "Qwen3-VL-8B": "ref", "GPT-5.6 Sol": "ref_6-sol", "GPT-6 Astra": "ref_gpt-6-astra"}
    rows = sorted([(lab, ref[REF_KEY[lab]], samp[sk]["mae"]) for lab, ck, sk, g, sh in MAP if lab in REF_KEY], key=lambda r: r[2])
    return pts, rows

def custo_vs_mae(pts):
    fig, ax = plt.subplots(figsize=(6.6, 4.0), dpi=300); fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
    ax.grid(color=GRID, lw=0.8); ax.set_axisbelow(True)
    for lab, c, mae, ci, g, sh in pts:
        col = {"A": C_A, "B": C_B, "V": C_V}[g]
        ax.plot([c, c], [ci[0], ci[1]], color=col, lw=1, alpha=.55, zorder=2)
        ax.scatter([c], [mae], s=70 if g != "A" else 110, color=col, marker="s" if sh else ("D" if g == "A" else "o"), edgecolors=SURF, linewidths=1.5, zorder=3)
    ax.set_xscale("log"); ax.set_xlim(20, 70000); ax.set_ylim(0.3, 1.35)
    ax.set_xlabel("Custo projetado por loja (US$/mês, 360 h de vídeo, escala log)"); ax.set_ylabel("MAE de contagem — vídeo principal (menor é melhor)")
    ax.set_xticks([30, 100, 300, 1000, 3000, 10000, 30000]); ax.set_xticklabels(["30", "100", "300", "1 mil", "3 mil", "10 mil", "30 mil"])
    pos = {"Pipeline A (ByteTrack)": (0, 12, "center"), "Gemma 4 26B": (0, 10, "center"), "Gemma 4 31B": (0, -14, "center"), "Qwen3-VL-8B": (0, -14, "center"),
           "GPT-5.6 Luna": (0, 10, "center"), "Claude Haiku 4.5": (0, 10, "center"), "Grok 4.6": (0, -14, "center"), "GPT-5.6 Terra": (0, 10, "center"),
           "Claude Sonnet 5": (0, -14, "center"), "GPT-5.6 Sol": (-7, 9, "right"), "Claude Opus 5": (7, 9, "left"), "GPT-6 Astra": (0, -14, "center"),
           "Pegasus 1.2 (vídeo nativo)": (0, 10, "center")}
    for lab, c, mae, ci, g, sh in pts:
        dx, dy, ha = pos[lab]; ax.annotate(lab, (c, mae), xytext=(dx, dy), textcoords="offset points", ha=ha, fontsize=7, color=INK2)
    leg = [Line2D([0], [0], marker="D", color="none", markerfacecolor=C_A, ms=8, label="Pipeline A (geométrico)"),
           Line2D([0], [0], marker="o", color="none", markerfacecolor=C_B, ms=8, label="Pipeline B — MLLM por quadros, gerenciado"),
           Line2D([0], [0], marker="s", color="none", markerfacecolor=C_B, ms=8, label="Pipeline B — MLLM por quadros, auto-hospedado"),
           Line2D([0], [0], marker="o", color="none", markerfacecolor=C_V, ms=8, label="Pipeline B — vídeo nativo")]
    ax.legend(handles=leg, loc="lower left", frameon=False, fontsize=7, labelcolor=INK2, borderaxespad=0.3)
    ax.text(0.99, 0.02, "barras verticais = IC 95% (bootstrap, 150 contagens)", transform=ax.transAxes, ha="right", fontsize=6.5, color=MUTED)
    fig.tight_layout(); fig.savefig(OUT / "fig_custo_vs_mae.png", facecolor=SURF); plt.close(fig)

def mae_ref_vs_main(rows):
    fig, ax = plt.subplots(figsize=(6.6, 4.4), dpi=300); fig.patch.set_facecolor(SURF); ax.set_facecolor(SURF)
    ax.grid(axis="x", color=GRID, lw=0.8); ax.set_axisbelow(True)
    for i, (lab, mr, mm) in enumerate(rows):
        ax.plot([mr, mm], [i, i], color=GRID, lw=2, zorder=1)
        ax.scatter([mr], [i], s=60, color="#9ec5f4", edgecolors=SURF, linewidths=1.5, zorder=3)
        ax.scatter([mm], [i], s=60, color="#1c5cab", edgecolors=SURF, linewidths=1.5, zorder=3)
    ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows], color=INK2); ax.invert_yaxis()
    ax.set_xlabel("MAE de contagem de pessoas (menor é melhor)"); ax.set_xlim(0.3, 1.4); ax.set_ylim(len(rows) - 0.4, -1.1)
    ax.axvline(0.800, color=C_A, lw=1.2, ls=(0, (4, 3)), zorder=2)
    ax.text(0.81, -0.75, "Pipeline A (ByteTrack) no vídeo principal: 0,80", fontsize=6.8, color=C_A, va="center")
    leg = [Line2D([0], [0], marker="o", color="none", markerfacecolor="#9ec5f4", ms=8, label="vídeo de referência (2024, borrado; verdade de referência densa)"),
           Line2D([0], [0], marker="o", color="none", markerfacecolor="#1c5cab", ms=8, label="vídeo principal (2026, nítido; validação por amostragem)")]
    fig.legend(handles=leg, loc="lower center", ncol=1, frameon=False, fontsize=7, labelcolor=INK2, bbox_to_anchor=(0.55, 0.0))
    fig.tight_layout(rect=(0, 0.09, 1, 1)); fig.savefig(OUT / "fig_mae_ref_vs_main.png", facecolor=SURF); plt.close(fig)

if __name__ == "__main__":
    zonas(); pts, rows = dados(); custo_vs_mae(pts); mae_ref_vs_main(rows)
    print("figuras em", OUT)
