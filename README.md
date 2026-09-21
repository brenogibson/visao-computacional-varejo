# Visão Computacional no Varejo — artefatos experimentais do TCC

Código, configurações e resultados do TCC **"Análise da Viabilidade e Implementação Prática de Sistemas de Visão Computacional no Varejo: Abordagens Tecnológicas para Extração e Processamento de Dados Comportamentais"** (MBA em Inteligência Artificial e Big Data, ICMC/USP, 2026).

O trabalho compara, sobre gravações reais de CFTV de uma loja de vestuário, duas abordagens de extração de métricas comportamentais:

- **Pipeline A** — visão computacional tradicional: YOLO26 (detecção) + rastreadores multiobjeto (BoxMOT) + heurísticas de pós-processamento de trajetórias + re-identificação;
- **Pipeline B** — modelos multimodais de linguagem em regime *zero-shot* (11 modelos via Amazon Bedrock/bedrock-mantle e vLLM auto-hospedado) + modalidade de vídeo nativo.

Ambas produzem o mesmo esquema canônico de métricas e são avaliadas em seis dimensões (acurácia, custo, tempo, complexidade, flexibilidade, privacidade).

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `src/retailcv/schema.py` | Esquema canônico de métricas (Pydantic) |
| `src/retailcv/video.py` | Ingestão: SHA-256, ffprobe, amostragem por PTS |
| `src/retailcv/detect.py`, `track.py` | Detecção com cache e rastreamento (BoxMOT) sobre o cache |
| `src/retailcv/postprocess.py` | 4 heurísticas de trajetória (ablação incremental) |
| `src/retailcv/reid_gallery.py` | Re-identificação na mesma câmera (OSNet) |
| `src/retailcv/pipeline_b/` | Esquema por quadro, clientes unificados (Anthropic / OpenAI-compat / vLLM), executor paralelo |
| `src/retailcv/insights/agent.py` | Agente de inteligência analítica (bateria pré-registrada de 10 consultas) |
| `configs/zones/*.json` | Polígonos das zonas por vídeo (ponto-pé + prioridade) |
| `scripts/cloud_*_job.sh` | Jobs de nuvem auto-terminantes (EC2 user-data) de cada fase experimental |
| `scripts/eval_*.py`, `make_report.py` | Avaliação (TrackEval, MAE/IC bootstrap, eventos HOI) e relatório consolidado |
| `scripts/make_sampling_kit.py` | Kit de validação por amostragem (HTML local) |
| `docs/` | Resultados consolidados, comparativo do agente e diagramas das zonas |

## Reprodutibilidade e dados

Toda execução experimental ocorreu em nuvem (AWS us-east-1), em instâncias efêmeras encerradas automaticamente, com versões de bibliotecas congeladas (`requirements.lock`) e identificador de execução por job. Os números da monografia são rastreáveis aos artefatos de execução.

**Os vídeos de CFTV, quadros extraídos e anotações que contenham imagens de pessoas não são distribuídos** (LGPD). Este repositório contém apenas código, configurações e artefatos derivados sem imagens (métricas agregadas, saídas de rastreamento em formato MOT, polígonos de zonas). Os diagramas em `docs/` mostram exclusivamente os polígonos, sem quadros de vídeo.

## Ambiente

Python ≥ 3.10; `pip install -e .` (ver `pyproject.toml`). O TrackEval exige ambiente separado com `numpy<1.24` (`eval-env/requirements.txt`). Os jobs de nuvem assumem credenciais AWS com acesso a Bedrock, EC2 e a um bucket S3 próprio (ajuste `BUCKET` nos scripts).

## Licença

AGPL-3.0 — imposta pelas dependências `ultralytics` e `boxmot` (ambas AGPL-3.0).
