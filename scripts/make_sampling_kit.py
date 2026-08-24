"""Gera o kit de validação por amostragem (seção 7.7 da metodologia).

30 janelas de 30s por vídeo longo, sorteio estratificado por terço (seed fixa,
pré-registrada), clipes cortados da sequência oficial 5 fps e página HTML local
com player + campos de contagem em 5 instantes fixos + export das respostas em JSON.
"""
from __future__ import annotations

import json
import random
import subprocess
import sys
from pathlib import Path

SEED = 42
N_PER_THIRD = 10
WIN = 30.0
INSTANTS = [0.0, 7.5, 15.0, 22.5, 30.0]


def sample_windows(duration: float, rng: random.Random) -> list[float]:
    starts: list[float] = []
    third = duration / 3
    for k in range(3):
        lo, hi = k * third, min((k + 1) * third, duration - WIN)
        got: list[float] = []
        tries = 0
        while len(got) < N_PER_THIRD and tries < 10000:
            s = rng.uniform(lo, hi)
            if all(abs(s - g) >= WIN for g in got):  # sem sobreposição
                got.append(s)
            tries += 1
        starts.extend(sorted(got))
    return starts


def cut_clip(video: str, start: float, out: Path) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.1f}", "-t", str(WIN),
                    "-i", video, "-vf", "scale=960:-2", "-c:v", "libx264", "-crf", "26",
                    "-movflags", "+faststart", "-an", str(out), "-y"], check=True)


HTML_HEAD = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Validação por amostragem — {label}</title><style>
body{{font-family:system-ui,sans-serif;max-width:1060px;margin:20px auto;padding:0 16px;background:#fafafa}}
.card{{background:#fff;border:1px solid #ddd;border-radius:10px;padding:14px;margin:18px 0}}
video{{width:100%;border-radius:6px;background:#000}}
.row{{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:8px}}
.inst{{display:flex;flex-direction:column;align-items:center;gap:3px}}
.inst button{{padding:4px 10px;border:1px solid #888;border-radius:6px;background:#eef;cursor:pointer}}
.inst input{{width:64px;padding:6px;text-align:center;font-size:16px;border:1px solid #aaa;border-radius:6px}}
.done{{outline:3px solid #2ecc71}}
#exportar{{position:fixed;bottom:18px;right:18px;padding:12px 20px;font-size:16px;background:#2c7be5;color:#fff;border:0;border-radius:8px;cursor:pointer}}
.prog{{position:fixed;bottom:22px;left:18px;font-size:14px;color:#555}}
h1{{font-size:20px}} .hint{{color:#666;font-size:14px}}
</style></head><body>
<h1>Validação por amostragem — {label}</h1>
<p class="hint">Para cada clipe: clique no botão do instante (o vídeo salta e pausa), conte as pessoas
visíveis (inclua parcialmente ocluídas/ao fundo) e digite o número. Repita nos 5 instantes.
Ao final, clique <b>Exportar respostas</b> e salve o arquivo NA MESMA PASTA. Seed do sorteio: {seed}.</p>
"""

HTML_TAIL = """
<button id="exportar">Exportar respostas</button><div class="prog" id="prog"></div>
<script>
const META = __META__;
function upd(){const t=document.querySelectorAll('input').length;
const f=[...document.querySelectorAll('input')].filter(i=>i.value!=='').length;
document.getElementById('prog').textContent=`${f}/${t} contagens preenchidas`;}
document.addEventListener('input',e=>{if(e.target.tagName==='INPUT'){e.target.classList.toggle('done',e.target.value!=='');upd();}});
function seek(id,t){const v=document.getElementById('v'+id);v.currentTime=t;v.pause();}
document.getElementById('exportar').onclick=()=>{
  const out={video:META.video,seed:META.seed,exported_at:new Date().toISOString(),windows:[]};
  META.windows.forEach((w,i)=>{const counts=META.instants.map((t,j)=>{
    const el=document.querySelector(`#v${i}`).closest('.card').querySelectorAll('input')[j];
    return el.value===''?null:parseInt(el.value);});
    out.windows.push({idx:i,start_s:w,counts:counts});});
  const blob=new Blob([JSON.stringify(out,null,1)],{type:'application/json'});
  const a=document.createElement('a');a.href=URL.createObjectURL(blob);
  a.download='respostas_'+META.video+'.json';a.click();};
upd();
</script></body></html>"""


def make_html(label: str, video_key: str, starts: list[float], out_dir: Path) -> None:
    cards = []
    for i, s in enumerate(starts):
        insts = "".join(
            f'<div class="inst"><button onclick="seek({i},{t})">{str(t).replace(".", ",")}s</button>'
            f'<input type="number" min="0" max="30" placeholder="?"></div>'
            for t in INSTANTS)
        mm, ss = divmod(int(s), 60)
        cards.append(
            f'<div class="card"><b>Janela {i + 1}/30</b> — início em {mm}m{ss:02d}s do vídeo<br>'
            f'<video id="v{i}" src="clips_{video_key}/w{i:02d}.mp4" controls preload="none"></video>'
            f'<div class="row">{insts}</div></div>')
    meta = {"video": video_key, "seed": SEED, "instants": INSTANTS,
            "windows": [round(s, 1) for s in starts]}
    html = (HTML_HEAD.format(label=label, seed=SEED) + "\n".join(cards)
            + HTML_TAIL.replace("__META__", json.dumps(meta)))
    (out_dir / f"validacao_{video_key}.html").write_text(html, encoding="utf-8")


def main(main_mp4: str, scale_mp4: str, out: str) -> None:
    out_dir = Path(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {"seed": SEED, "window_s": WIN, "instants": INSTANTS, "videos": {}}
    for video, key, label in [(main_mp4, "main", "vídeo principal (37 min)"),
                              (scale_mp4, "scale", "vídeo de escalabilidade (67 min)")]:
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                    "-of", "csv=p=0", video], capture_output=True, text=True).stdout)
        rng = random.Random(f"{SEED}-{key}")
        starts = sample_windows(dur, rng)
        clip_dir = out_dir / f"clips_{key}"
        clip_dir.mkdir(exist_ok=True)
        for i, s in enumerate(starts):
            cut_clip(video, s, clip_dir / f"w{i:02d}.mp4")
        make_html(label, key, starts, out_dir)
        manifest["videos"][key] = {"duration_s": dur, "starts": [round(s, 1) for s in starts]}
        print(f"{key}: {len(starts)} janelas", flush=True)
    (out_dir / "manifest_sorteio.json").write_text(json.dumps(manifest, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
