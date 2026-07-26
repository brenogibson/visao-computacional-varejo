# retail-cv — experimentos do TCC

Comparação: visão computacional tradicional (YOLO26+BoxMOT) vs MLLM zero-shot (Bedrock/mantle)
para métricas comportamentais de varejo. Ver `/mnt/c/Users/breno/TCC2/PLANO_EXECUCAO.md`.

- `src/retailcv/schema.py` — schema canônico v1 (Pydantic)
- `src/retailcv/video.py` — ingestão: SHA-256, ffprobe, amostragem por PTS
- `src/retailcv/runlog.py` — registro de execução (reprodutibilidade)
- `scripts/pilot_*.py` — pilotos do mantle (validados 26/07/2026, ver docs/RESULTADOS_PILOTO.md)

Perfil AWS: `automations` (us-east-1). Vídeos: `s3://video-analytics-store`.
