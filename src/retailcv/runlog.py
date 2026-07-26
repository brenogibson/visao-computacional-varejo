"""Registro de execução (reprodutibilidade — seção 3.9 da metodologia).

Cada execução experimental gera um run_id = <data>-<git_sha>-<seed> e um registro JSON
com config, versões de pacotes, hash dos vídeos e custo medido. Regra de paridade:
comparações só valem entre runs que diferem em exatamente 1 eixo (verificada por script).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

TRACKED_PACKAGES = ["ultralytics", "boxmot", "supervision", "pydantic", "anthropic", "openai", "boto3"]


def git_sha(repo: str | Path = ".") -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=repo,
                              capture_output=True, text=True, check=True).stdout.strip()
    except subprocess.CalledProcessError:
        return "nogit"


def package_versions() -> dict[str, str]:
    vers = {}
    for pkg in TRACKED_PACKAGES:
        try:
            vers[pkg] = metadata.version(pkg)
        except metadata.PackageNotFoundError:
            vers[pkg] = "absent"
    return vers


def new_run(config_path: str | Path, seed: int, out_root: str | Path = "runs") -> Path:
    """Cria o diretório do run e grava o registro inicial. Retorna o diretório."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = f"{ts}-{git_sha()}-s{seed}"
    run_dir = Path(out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    record = {
        "run_id": run_id,
        "created_utc": ts,
        "config": str(config_path),
        "config_content": Path(config_path).read_text() if Path(config_path).exists() else None,
        "seed": seed,
        "python": sys.version,
        "packages": package_versions(),
        "cost_usd": None,          # preenchido ao final (tokens reais ou GPU-horas)
        "wall_time_s": None,
    }
    (run_dir / "runlog.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
    return run_dir


def finalize_run(run_dir: str | Path, cost_usd: float | None, wall_time_s: float) -> None:
    p = Path(run_dir) / "runlog.json"
    record = json.loads(p.read_text())
    record["cost_usd"] = cost_usd
    record["wall_time_s"] = wall_time_s
    p.write_text(json.dumps(record, indent=1, ensure_ascii=False))
