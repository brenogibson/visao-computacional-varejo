# Resultados preliminares — tabelas consolidadas

_Gerado automaticamente; preços de 23/08/2026 (endpoint regional us-east-1). Acurácia nos vídeos longos pendente da validação por amostragem._

## 1. Pipeline A — triagem de rastreadores (vídeo de referência, GT denso)

| tracker | MOTA | IDF1 | HOTA | IDSW | tempo (s) |
|---|---|---|---|---|---|
| bytetrack | 78.13 | 76.47 | 66.63 | 50 | 14.5 |
| hybridsort | 76.74 | 72.78 | 59.57 | 54 | 69.0 |
| botsort | 74.70 | 72.51 | 60.19 | 59 | 48.0 |
| boosttrack | 65.99 | 64.27 | 51.42 | 66 | 58.3 |
| deepocsort | 67.32 | 61.92 | 50.85 | 57 | 48.1 |
| ocsort | 61.87 | 54.86 | 46.69 | 47 | 14.6 |
| strongsort | 67.98 | 46.60 | 42.22 | 111 | 86.4 |

## 2. Pipeline B — acurácia no vídeo de referência (0,5 fps)

| modelo | MAE contagem | viés | erro ocupação zona | falhas schema |
|---|---|---|---|---|
| Qwen3-VL-8B (self-hosted) | 0.611 | -0.042 | 75% | 0 |
| Gemma 4 26B-A4B | 0.663 | -0.347 | 81% | 0 |
| Claude Sonnet 5 | 0.701 | +0.529 | 88% | 3 |
| GPT-5.6 Luna | 0.742 | +0.321 | 74% | 0 |
| GPT-5.6 Terra | 0.895 | +0.495 | 45% | 0 |
| Claude Opus 5 | 0.905 | +0.663 | 87% | 0 |
| Grok 4.6 | 1.011 | +0.842 | 91% | 0 |
| GPT-5.6 Sol | 1.137 | +0.821 | 85% | 0 |
| GPT-6 Astra | 1.242 | +1.105 | 78% | 0 |
| Claude Haiku 4.5 | 1.253 | +1.074 | 79% | 0 |
| Gemma 4 31B | 1.326 | -1.295 | 68% | 0 |

## 3. Custo e tempo REAIS — vídeo principal (36,6 min) por abordagem

| abordagem | custo do vídeo (US$) | tempo (s) | US$/h de vídeo | US$/mês (360h) |
|---|---|---|---|---|
| Pipeline A (YOLO26m+bytetrack, GPU) | 0.057 | 255 | 0.093 | 34 |
| Pipeline A + ReID (teto) | 0.079 | 354 | 0.130 | 47 |
| B: Gemma 4 31B | 0.173 | 541 | 0.283 | 102 |
| B: Gemma 4 26B-A4B | 0.177 | 205 | 0.290 | 104 |
| B: Qwen3-VL-8B self-hosted (GPU) | 1.335 | 4661 | 2.189 | 788 |
| B: GPT-5.6 Luna | 1.396 | 677 | 2.288 | 824 |
| B: Claude Haiku 4.5 | 5.134 | 261 | 8.417 | 3030 |
| B: Grok 4.6 | 9.343 | 2758 | 15.317 | 5514 |
| B: GPT-5.6 Terra | 11.790 | 587 | 19.328 | 6958 |
| B: Claude Sonnet 5 | 12.128 | 588 | 19.883 | 7158 |
| B: GPT-5.6 Sol (tarifa cheia: 39.833 / 23508/mês) | 28.688 | 1168 | 47.029 | 16931 |
| B: Claude Opus 5 | 32.536 | 539 | 53.338 | 19202 |
| B: GPT-6 Astra | 57.971 | 1246 | 95.034 | 34212 |
| B3: Pegasus 1.2 (vídeo-nativo) | 1.076 | 299 | 1.764 | 635 |

_Extrapolação: 12h de operação/dia × 30 dias = 360h de vídeo/mês por loja. Custo do Pipeline B a 0,5 fps; taxas maiores escalam ~linearmente. Pipeline A assume instância dedicada apenas durante o processamento (batch)._

## 4. Eixo B3 — vídeo-nativo (Pegasus 1.2, 37 clipes de 60s)

- Clipes processados: 37/37; tempo total 299s
- Interações pessoa-produto detectadas: 291 (validação contra eventos BORIS pendente)
- Únicos por clipe (soma, com dupla contagem entre clipes): 99 — limitação do fatiamento a declarar

## 5. Complexidade de implementação (contagens objetivas até 23/08)

| indicador | Pipeline A | Pipeline B (gerenciado) | B self-hosted |
|---|---|---|---|
| falhas de infra/ambiente no projeto | 4 (ffmpeg/DLAMI, CVAT MOT ×2, API boxmot) | 1 (CLI ausente em AMI) | 2 (ninja/vLLM, capacidade GPU) |
| falhas de schema/modelo | — | 91 frames (só Sonnet 5; limitação documentada) | 0 |
| dependências de runtime | torch, ultralytics, boxmot, TrackEval (numpy<1.24!) | 2 SDKs HTTP | vllm + torch + GPU |
| hardware dedicado | GPU | nenhum | GPU |

## 6. Validação por amostragem — vídeo principal (150 contagens do autor, seed 42, critério inclusivo v2)

| abordagem | MAE | viés | IC95% do MAE |
|---|---|---|---|
| B: GPT-6 Astra | 0.440 | +0.093 | [0.340, 0.547] |
| B: Grok 4.6 | 0.487 | -0.087 | [0.387, 0.587] |
| B: Qwen3-VL-8B self-hosted | 0.500 | -0.020 | [0.400, 0.600] |
| B: GPT-5.6 Luna | 0.620 | -0.420 | [0.513, 0.733] |
| B: Claude Sonnet 5 | 0.655 | -0.338 | [0.532, 0.784] |
| B: GPT-5.6 Sol | 0.660 | -0.073 | [0.540, 0.793] |
| B: Claude Opus 5 | 0.667 | -0.200 | [0.553, 0.787] |
| B: GPT-5.6 Terra | 0.707 | -0.320 | [0.600, 0.820] |
| A: bytetrack (E0) | 0.800 | -0.280 | [0.687, 0.920] |
| A: bytetrack +heurísticas (P4) | 0.800 | -0.213 | [0.687, 0.920] |
| A: hybridsort (E0) | 0.833 | -0.180 | [0.720, 0.947] |
| B: Claude Haiku 4.5 | 0.860 | -0.167 | [0.733, 0.987] |
| B: Gemma 4 31B | 0.873 | -0.633 | [0.747, 1.000] |
| B: Gemma 4 26B-A4B | 0.900 | -0.020 | [0.773, 1.027] |
| B3: Pegasus vídeo-nativo (n=150, tol. 5s) | 1.200 | -1.000 | [1.033, 1.373] |

_Sensibilidade à definição (v1 estrito × v2 inclusivo): 96/150 instantes mudaram (+143 pessoas parciais, +41%); o ranking muda substancialmente entre critérios — ver DECISOES.md D16._
