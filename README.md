# retail-cv — experimentos do TCC

Comparação: visão computacional tradicional (YOLO26+BoxMOT) vs MLLM zero-shot (Bedrock/mantle)
para métricas comportamentais de varejo. Ver `/mnt/c/Users/breno/TCC2/PLANO_EXECUCAO.md`.

- `src/retailcv/schema.py` — schema canônico v1 (Pydantic)
- `src/retailcv/video.py` — ingestão: SHA-256, ffprobe, amostragem por PTS
- `src/retailcv/runlog.py` — registro de execução (reprodutibilidade)
- `scripts/pilot_*.py` — pilotos do mantle (validados 26/07/2026, ver docs/RESULTADOS_PILOTO.md)

Execução: AWS us-east-1 (EC2 GPU efêmeras + Amazon Bedrock). Os vídeos de CFTV e as anotações contendo imagens de pessoas NÃO são distribuídos (LGPD); apenas artefatos derivados sem imagens (métricas, saídas MOT, zonas) são reproduzíveis a partir do código.
