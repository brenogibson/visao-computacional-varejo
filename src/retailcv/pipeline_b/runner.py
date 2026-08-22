"""Runner do Pipeline B: amostra frames por tempo, envia ao MLLM em paralelo e grava
JSONL bruto por frame + resumo de usage/custo/latência.

Saída por run: <out_dir>/frames.jsonl (1 linha por frame: t, resposta, usage, wall)
               <out_dir>/run_summary.json
"""
from __future__ import annotations

import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .clients import make_client
from .frame_schema import build_prompt


def sample_frames(video: str, fps: float, out_dir: Path) -> list[tuple[float, Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"fps={fps}",
                    "-q:v", "3", str(out_dir / "f_%06d.jpg"), "-y"], check=True)
    frames = sorted(out_dir.glob("f_*.jpg"))
    return [(i / fps, p) for i, p in enumerate(frames)]


def run_model(video: str, video_key: str, model_id: str, fps: float,
              out_dir: str | Path, workers: int = 8, max_retries: int = 1) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    frames = sample_frames(video, fps, out_dir / "frames_tmp")
    prompt = build_prompt(video_key)
    client = make_client(model_id, prompt)

    results: dict[int, dict] = {}
    failures = 0

    def work(i: int, t: float, path: Path):
        jpeg = path.read_bytes()
        last_err = None
        for attempt in range(max_retries + 1):
            try:
                out, usage, wall = client.analyze_frame(jpeg)
                return i, {"t": round(t, 2), "ok": True, "attempts": attempt + 1,
                           "result": out, "usage": usage, "wall_s": round(wall, 2)}
            except Exception as e:  # noqa: BLE001 — falha de schema/API vira métrica
                last_err = str(e)[:200]
                if "401" in last_err or "expired" in last_err.lower():
                    try:
                        client.refresh_token()
                    except AttributeError:
                        pass
                time.sleep(2 * (attempt + 1))
        return i, {"t": round(t, 2), "ok": False, "error": last_err}

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(work, i, t, p) for i, (t, p) in enumerate(frames)]
        for fut in as_completed(futs):
            i, rec = fut.result()
            results[i] = rec
            if not rec["ok"]:
                failures += 1
    wall_total = time.time() - t0

    with open(out_dir / "frames.jsonl", "w") as f:
        for i in sorted(results):
            f.write(json.dumps(results[i], ensure_ascii=False) + "\n")

    oks = [r for r in results.values() if r["ok"]]
    summary = {
        "model_id": model_id, "video": video, "video_key": video_key, "fps": fps,
        "n_frames": len(frames), "n_ok": len(oks), "n_failures": failures,
        "wall_total_s": round(wall_total, 1),
        "input_tokens": sum(r["usage"]["input_tokens"] for r in oks),
        "output_tokens": sum(r["usage"]["output_tokens"] for r in oks),
        "reasoning_tokens": sum(r["usage"].get("reasoning_tokens", 0) for r in oks),
        "mean_latency_s": round(sum(r["wall_s"] for r in oks) / max(len(oks), 1), 2),
        "retries_used": sum(r.get("attempts", 1) - 1 for r in oks),
    }
    json.dump(summary, open(out_dir / "run_summary.json", "w"), indent=1)
    return summary
