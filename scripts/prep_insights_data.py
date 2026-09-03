"""Prepara os datasets canônicos da etapa agêntica (vídeo principal).

Pipeline A: bytetrack + heurísticas + ReID (E3) + zonas main.json → ocupação, únicos,
permanência por visita, fluxo temporal. Interações: indisponível (declarado).
Pipeline B: Grok 4.6 (melhor MAE na amostragem v2) → ocupação por zona do modelo,
fluxo temporal, interações (eventos deduplicados). Únicos: indisponível.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from shapely.geometry import Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data"
FPS_A = 5.0
WIN = 300  # janela de fluxo (5 min)

zcfg = json.load(open(ROOT / "configs/zones/main.json"))
polys = {n: Polygon(p) for n, p in zcfg["zones"].items()}
prio = zcfg["priority_order"]


def zone_of(x: float, y: float) -> str:
    p = Point(x, y)
    for n in prio:
        if polys[n].contains(p):
            return n
    return "fora_de_zona"


# ---------------- Pipeline A ----------------
tracks = defaultdict(list)  # tid -> [(frame, zone)]
for line in open(D / "a2/a2_out/bytetrack/E3_reid.txt"):
    p = line.split(",")
    f, tid = int(p[0]), int(p[1])
    x, y, w, h = (float(v) for v in p[2:6])
    tracks[tid].append((f, zone_of(x + w / 2, y + h)))

occ = defaultdict(float)
uniq = defaultdict(set)
visits = defaultdict(list)  # zona -> duração de cada visita (s)
flow = defaultdict(set)     # janela -> ids
counts = defaultdict(int)   # frame -> pessoas
for tid, obs in tracks.items():
    obs.sort()
    cur_zone, cur_len = None, 0
    for f, z in obs:
        occ[z] += 1 / FPS_A
        uniq[z].add(tid)
        flow[int((f / FPS_A) // WIN)].add(tid)
        counts[f] += 1
        if z == cur_zone:
            cur_len += 1
        else:
            if cur_zone is not None and cur_len >= 3:
                visits[cur_zone].append(cur_len / FPS_A)
            cur_zone, cur_len = z, 1
    if cur_zone is not None and cur_len >= 3:
        visits[cur_zone].append(cur_len / FPS_A)

frames_total = max(counts) if counts else 0
timeline = []
for wi in sorted(flow):
    fr = [counts.get(f, 0) for f in range(int(wi * WIN * FPS_A) + 1, int((wi + 1) * WIN * FPS_A) + 1)]
    timeline.append({"janela_min": f"{wi*5}-{(wi+1)*5}", "visitantes_unicos": len(flow[wi]),
                     "pessoas_media": round(sum(fr) / max(len(fr), 1), 2), "pessoas_pico": max(fr, default=0)})

dataset_a = {
    "pipeline": "A (YOLO26m + bytetrack + heurísticas + ReID OSNet)",
    "video": "principal (36,6 min, loja de vestuário, 02/05/2026 à tarde)",
    "zonas": sorted(polys),
    "ocupacao_por_zona_pessoa_segundos": {z: round(v, 1) for z, v in sorted(occ.items())},
    "visitantes_unicos_total": len(tracks),
    "visitantes_unicos_por_zona": {z: len(s) for z, s in sorted(uniq.items())},
    "permanencia_media_por_visita_s": {z: round(sum(v) / len(v), 1) for z, v in sorted(visits.items()) if v},
    "n_visitas_por_zona": {z: len(v) for z, v in sorted(visits.items())},
    "fluxo_temporal_janelas_5min": timeline,
    "interacoes_com_produto": "INDISPONÍVEL neste pipeline (detecção+rastreamento não classifica ações)",
}
json.dump(dataset_a, open(D / "insights_dataset_A.json", "w"), ensure_ascii=False, indent=1)

# ---------------- Pipeline B (Grok 4.6) ----------------
occ_b = defaultdict(float)
counts_b = defaultdict(list)
inter_raw = []
DT = 2.0
for line in open(D / "b2ext/b2_out/main_6/frames.jsonl"):
    r = json.loads(line)
    if not r.get("ok"):
        continue
    wi = int(r["t"] // WIN)
    counts_b[wi].append(r["result"]["people_count"])
    for person in r["result"]["people"]:
        occ_b[person["zone"]] += DT
        if person["action"] in ("pegando_produto", "devolvendo_produto", "examinando_produto"):
            inter_raw.append({"t": r["t"], "acao": person["action"], "zona": person["zone"]})

inter_raw.sort(key=lambda e: (e["acao"], e["zona"], e["t"]))
inter, last = [], {}
for e in inter_raw:
    k = (e["acao"], e["zona"])
    if k in last and e["t"] - last[k] <= DT + 0.1:
        last[k] = e["t"]
        continue
    last[k] = e["t"]
    inter.append(e)

timeline_b = [{"janela_min": f"{wi*5}-{(wi+1)*5}",
               "pessoas_media": round(sum(v) / len(v), 2), "pessoas_pico": max(v)}
              for wi, v in sorted(counts_b.items())]
inter_por_zona = defaultdict(lambda: defaultdict(int))
for e in inter:
    inter_por_zona[e["zona"]][e["acao"]] += 1

dataset_b = {
    "pipeline": "B (MLLM zero-shot Grok 4.6, frames a 0,5 fps)",
    "video": "principal (36,6 min, loja de vestuário, 02/05/2026 à tarde)",
    "zonas": sorted(polys),
    "ocupacao_por_zona_pessoa_segundos": {z: round(v, 1) for z, v in sorted(occ_b.items())},
    "visitantes_unicos_total": "INDISPONÍVEL neste pipeline (análise frame a frame não mantém identidade)",
    "permanencia_media_por_visita_s": "INDISPONÍVEL neste pipeline (sem identidade)",
    "fluxo_temporal_janelas_5min": timeline_b,
    "interacoes_com_produto_eventos": inter,
    "interacoes_por_zona_resumo": {z: dict(a) for z, a in sorted(inter_por_zona.items())},
    "ressalva_interacoes": "eventos discretos subestimados (revocação ~0,1-0,3 medida vs gabarito humano)",
}
json.dump(dataset_b, open(D / "insights_dataset_B.json", "w"), ensure_ascii=False, indent=1)

print("A:", {k: dataset_a[k] for k in ["visitantes_unicos_total"]},
      "| zonas occ:", list(dataset_a["ocupacao_por_zona_pessoa_segundos"].items())[:3])
print("B: interações deduplicadas:", len(inter), "| janelas:", len(timeline_b))
