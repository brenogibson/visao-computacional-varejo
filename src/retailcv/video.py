"""Ingestão de vídeo: hash de integridade, metadados via ffprobe e amostragem por TEMPO (PTS).

Decisão D11: fps heterogêneo entre os vídeos (30 vs ~7 variável) → toda conversão
frame→tempo usa PTS; amostragem é por segundos, nunca por índice de frame.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoInfo:
    path: str
    sha256: str
    duration_s: float
    width: int
    height: int
    codec: str
    nb_frames: int


def sha256_of(path: str | Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while data := f.read(chunk):
            h.update(data)
    return h.hexdigest()


def probe(path: str | Path) -> VideoInfo:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height,nb_frames",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    j = json.loads(out.stdout)
    s, f = j["streams"][0], j["format"]
    return VideoInfo(
        path=str(path), sha256=sha256_of(path),
        duration_s=float(f["duration"]),
        width=int(s["width"]), height=int(s["height"]),
        codec=s["codec_name"], nb_frames=int(s.get("nb_frames", 0)),
    )


def sample_frames(path: str | Path, out_dir: str | Path, fps: float, quality: int = 2) -> list[tuple[float, Path]]:
    """Extrai frames a `fps` constantes por tempo. Retorna [(t_seconds, jpg_path)].

    Usa o filtro fps do ffmpeg (baseado em PTS) e nomeia cada arquivo pelo timestamp,
    garantindo rastreabilidade frame→instante independentemente do fps nativo.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path), "-vf", f"fps={fps}",
         "-frame_pts", "1", "-q:v", str(quality), str(out_dir / "f_%06d.jpg"), "-y"],
        check=True,
    )
    frames = sorted(out_dir.glob("f_*.jpg"))
    return [(i / fps, p) for i, p in enumerate(frames)]
