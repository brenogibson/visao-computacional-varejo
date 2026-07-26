"""Avaliação da triagem (Fase A1): monta a árvore do TrackEval e calcula MOTA/IDF1/HOTA
para os 7 trackers contra o ground truth anotado no CVAT.

Roda LOCALMENTE (exceção D13: análise estatística sobre artefatos já extraídos).
Requer venv separado com numpy<1.24 (TrackEval abandonado) — ver eval-env/.

Uso:
  python scripts/eval_screening.py --gt data/gt_ref.txt --trackers-dir data/trackers_out --out runs/screening_eval
"""
from __future__ import annotations

import argparse
import configparser
import shutil
import subprocess
import sys
from pathlib import Path

SEQ = "LOJA-01"
BENCH = "LOJA"
TRACKERS = ["bytetrack", "ocsort", "botsort", "deepocsort", "strongsort", "boosttrack", "hybridsort"]


def build_tree(gt_txt: Path, trackers_dir: Path, work: Path, seq_len: int, fps: int = 5) -> tuple[Path, Path]:
    gt_root = work / "gt" / "mot_challenge"
    tr_root = work / "trackers" / "mot_challenge"
    seq_dir = gt_root / f"{BENCH}-train" / SEQ
    seq_dir.joinpath("gt").mkdir(parents=True, exist_ok=True)
    shutil.copy(gt_txt, seq_dir / "gt" / "gt.txt")

    ini = configparser.ConfigParser()
    ini["Sequence"] = {"name": SEQ, "imDir": "img1", "frameRate": str(fps),
                       "seqLength": str(seq_len), "imWidth": "1920", "imHeight": "1080",
                       "imExt": ".jpg"}
    with open(seq_dir / "seqinfo.ini", "w") as f:
        ini.write(f)

    seqmaps = gt_root / "seqmaps"
    seqmaps.mkdir(parents=True, exist_ok=True)
    (seqmaps / f"{BENCH}-train.txt").write_text(f"name\n{SEQ}\n")

    for t in TRACKERS:
        src = trackers_dir / t / "ref.txt"
        if not src.exists():
            print(f"aviso: {src} ausente, pulando {t}")
            continue
        dst = tr_root / f"{BENCH}-train" / t / "data"
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst / f"{SEQ}.txt")
    return gt_root, tr_root


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", required=True, type=Path)
    ap.add_argument("--trackers-dir", required=True, type=Path)
    ap.add_argument("--trackeval-repo", type=Path, default=Path.home() / "TrackEval")
    ap.add_argument("--out", type=Path, default=Path("runs/screening_eval"))
    ap.add_argument("--seq-len", type=int, required=True)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    gt_root, tr_root = build_tree(args.gt, args.trackers_dir, args.out, args.seq_len)

    trackers_present = [t for t in TRACKERS if (tr_root / f"{BENCH}-train" / t).exists()]
    cmd = [sys.executable, str(args.trackeval_repo / "scripts" / "run_mot_challenge.py"),
           "--GT_FOLDER", str(gt_root), "--TRACKERS_FOLDER", str(tr_root),
           "--BENCHMARK", BENCH, "--SPLIT_TO_EVAL", "train",
           "--TRACKERS_TO_EVAL", *trackers_present,
           "--METRICS", "HOTA", "CLEAR", "Identity",
           "--DO_PREPROC", "False", "--USE_PARALLEL", "False"]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
