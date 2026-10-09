# Documentação do projeto — reuso em outros ambientes

Guia para reaproveitar o código, os dados e o método do TCC *Análise da Viabilidade e Implementação Prática de Sistemas de Visão Computacional no Varejo* (MBA em IA e Big Data, ICMC/USP, 2026) em outros projetos, inclusive em servidores próprios. Complementa o `README.md` (visão geral) e a monografia (método e resultados).

Convenções: caminhos `s3://…` referem-se ao bucket privado `video-analytics-store` (conta AWS 522681761216, us-east-1); nada que contenha imagens de pessoas está no repositório público (LGPD).

---

## 1. O que o projeto faz

Extrai métricas comportamentais de clientes a partir de vídeo de CFTV de loja e as grava em um **esquema canônico** único, por duas vias:

| Pipeline | Etapas | Saída |
|---|---|---|
| **A — geométrico** | YOLO26 (detecção de pessoas) → rastreador BoxMOT → heurísticas de trajetória → re-identificação (OSNet) → atribuição de zona pelo ponto-pé | trajetórias MOT, contagem, ocupação por zona, permanência, visitantes únicos, mapa de calor |
| **B — multimodal** | amostragem de quadros (0,5 quadro/s) → MLLM *zero-shot* com saída JSON restrita (Bedrock/bedrock-mantle ou vLLM local) ou vídeo nativo (Pegasus) | contagem, zona declarada, ação por pessoa, eventos de interação |

Um agente de inteligência analítica consome o esquema canônico e responde a uma bateria pré-registrada de 10 consultas de negócio.

Resultados principais (loja de vestuário, 3 vídeos, 110 min): Pipeline A custa cerca de US$ 34/mês por loja e tem MAE de contagem 0,80 no vídeo principal; os melhores MLLMs chegam a MAE 0,44 a 0,55 por 1.000 a 34.000 US$/mês; MLLMs erram 45 a 91 % da ocupação por zona; eventos pontuais de interação falham em todas as abordagens a 0,5 quadro/s (revocação ≤ 0,27). Detalhes em `docs/RESULTADOS_PRELIMINARES.md` e na monografia.

## 2. Mapa dos artefatos

### 2.1 Repositório (`github.com/brenogibson/visao-computacional-varejo`)

| Caminho | Conteúdo |
|---|---|
| `src/retailcv/video.py` | `probe()` (ffprobe), `sha256_of()`, `sample_frames(path, out_dir, fps)` por PTS |
| `src/retailcv/detect.py` | `detect_video(video, out_npz, model_name="yolo26m.pt", conf=0.25, device="cuda:0")` → cache `.npz`; `load_cache()` |
| `src/retailcv/track.py` | `track_video(video, det_cache, tracker_name, out_txt, device, reid_weights)` → MOT txt (BoxMOT: bytetrack, hybridsort, botsort, ocsort, deepocsort, boosttrack, strongsort) |
| `src/retailcv/postprocess.py` | `parse_mot/dump_mot`; heurísticas `filter_min_length`, `filter_min_conf`, `interpolate_gaps`, `stitch_tracks`; `run_incremental(mot_in, out_dir)` gera P0…P4 |
| `src/retailcv/reid_gallery.py` | `run_reid(video, mot_in, mot_out, reid_weights="osnet_x1_0_msmt17.pt", sim_threshold=0.6)` |
| `src/retailcv/schema.py` | Esquema canônico Pydantic: `FrameObservation`, `PersonObservation`, `ZoneDwell`, `InteractionEvent`, `VideoMetrics` |
| `src/retailcv/pipeline_b/frame_schema.py` | Esquema JSON por quadro e `build_prompt(video_key)` (descrição textual das zonas) |
| `src/retailcv/pipeline_b/clients.py` | `make_client(model_id, prompt)`: Claude (Messages API, tool-use forçado), OpenAI-compat (GPT, Gemma, Grok), `VLLMLocalClient` |
| `src/retailcv/pipeline_b/runner.py` | `run_model(video, video_key, model_id, fps, out_dir, workers=8)` → `frames.jsonl` + `run_summary.json` (tokens, tempo) |
| `src/retailcv/insights/agent.py` | `run_battery(dataset_path)`: agente com ferramentas sobre o dataset canônico |
| `src/retailcv/runlog.py` | `new_run()/finalize_run()`: SHA do git, versões, semente, custo, tempo |
| `configs/zones/{ref,main,scale}.json` | Polígonos das zonas por leiaute (ver §4) |
| `scripts/cloud_*_job.sh` | Jobs EC2 auto-terminantes de cada fase (user-data); servem de receita de execução |
| `scripts/eval_screening.py` | MOTA/IDF1/HOTA via TrackEval (ambiente separado, `numpy<1.24`) |
| `scripts/eval_b1.py`, `eval_sampling.py`, `eval_iho.py` | MAE/viés por taxa; MAE com IC 95 % bootstrap; precisão/revocação de eventos e IoU de estados |
| `scripts/make_sampling_kit.py` | Kit HTML de validação por amostragem (30 janelas × 5 instantes, semente 42) |
| `scripts/make_report.py`, `make_figures.py` | Tabelas e figuras da monografia a partir dos artefatos |
| `scripts/prep_insights_data.py` | Monta os datasets canônicos A e B para o agente |
| `runs/screening_eval/` | Saídas MOT dos 7 rastreadores e métricas (sem imagens) |
| `requirements.lock`, `pyproject.toml` | Versões congeladas (ultralytics 8.4.106, boxmot 22.0.0, supervision 0.29.1) |

### 2.2 Bucket S3 (privado)

| Prefixo | Conteúdo |
|---|---|
| `projeto/` | **Kit de reuso** (este documento, código, anotações, vídeo borrado, documentação) — ver `projeto/MANIFEST.md` |
| `videos/derived/{ref,main,scale}_5fps.mp4` | Sequências oficiais a 5 quadros/s (reamostradas por tempo, `ffmpeg -vf fps=5 -crf 18`) |
| `blurredvideo.mp4` (raiz) | Vídeo de referência original, 6 min, faces borradas (leiaute 2024) |
| `WJCI…992.mp4.mp4`, `WJCI…477.mp4.mp4` (raiz) | Vídeos principal (37 min) e de escalabilidade (67 min), originais, sem borramento |
| `annotations/gt_ref_final.txt` | Verdade de referência MOT do vídeo borrado: 9.153 caixas, 42 identidades, quadros 1–1691 a 5 quadros/s |
| `annotations/preanno/` | Pré-anotação automática (YOLO26x + ByteTrack) usada como ponto de partida no CVAT |
| `tcc-backup/cvat/cvat_task1_backup.zip` | Backup da tarefa CVAT (restaurável em outra instalação do CVAT) |
| `tcc-backup/retail-cv/data/boris_eventos_ref.csv` | Eventos de interação (pegar, devolver, examinar) anotados no BORIS |
| `runs/{screening,a2,b1,b2,b2ext,b2ext2,b3,b3ref,b4,qwen,insights}/` | Saídas brutas de cada fase (MOT, `frames.jsonl`, sumários, logs de job) |
| `code/retailcv_src.tar.gz` | Fonte usado pelos jobs de nuvem |
| `tcc/` | Monografia (LaTeX, PDF, log de edições) |
| `tcc-backup/` | Backup integral (documentos, repositório, CVAT, BORIS, sessão do agente) |

## 3. Formatos de dados

**MOT (rastreamento e verdade de referência)**, uma linha por caixa:
```
frame, id, x, y, largura, altura, conf, classe, visibilidade
```
`frame` começa em 1 e refere-se à sequência oficial a 5 quadros/s (t = (frame−1)/5 s). IDs são pseudônimos opacos.

**Cache de detecção** (`det_*.npz`): um array por quadro com `x1, y1, x2, y2, conf, cls`; permite rodar vários rastreadores sem repetir a detecção (modo "só detecção" = o próprio cache).

**Pipeline B** (`frames.jsonl`): uma linha por quadro amostrado, `{"t": segundos, "ok": bool, "result": {"people_count": n, "people": [{"zone", "action", "interacting_with_product", "appearance"}]}, "usage": {...}}`. Ações: `circulando`, `examinando_produto`, `pegando_produto`, `devolvendo_produto`, `parado`, …

**Esquema canônico** (`schema.py`): `VideoMetrics{run_id, video_id, pipeline, frames[], zone_dwell[], interaction_events[], total_unique_visitors, heatmap_path}`. Campos que dependem de identidade ficam `null` quando a abordagem não a fornece (ex.: `unique_visitors` no Pipeline B).

**Eventos BORIS** (`boris_eventos_ref.csv`): `t_start, t_end, type, zone` com `type ∈ {pegar_produto, devolver_produto, examinar_produto}`.

## 4. Zonas de análise

Arquivo JSON por leiaute de câmera (`configs/zones/*.json`):
```json
{"resolution": [1920, 1080], "anchor": "bottom_center",
 "priority_order": ["mesa_central", "entrada", "corredor_esquerdo", "corredor_central", "corredor_direito", "caixa"],
 "zones": {"mesa_central": [[x, y], …], "entrada": [[x, y], …], …}}
```
Regra de atribuição: o **ponto-pé** (centro da base da caixa) é testado contra os polígonos na ordem de `priority_order`; a primeira zona que o contém vence; fora de todas → `fora_de_zona`. Para uma nova loja: desenhe os polígonos sobre um quadro da câmera (qualquer ferramenta; coordenadas em pixels da resolução nativa), defina a prioridade (zonas pequenas e sobrepostas primeiro) e gere o diagrama de conferência com `scripts/make_figures.py`. O Pipeline B recebe as zonas como descrição textual gerada por `build_prompt()`; ajuste o texto em `frame_schema.py` para o novo leiaute.

## 5. Executar em servidores próprios

### 5.1 Requisitos
- Linux, Python ≥ 3.12, ffmpeg; GPU NVIDIA (≥ 8 GB) para detecção, rastreamento com ReID e vLLM; CPU basta para pós-processamento, Pipeline B gerenciado e avaliações.
- `pip install -e .` no repositório (ou `pip install -r requirements.lock` para reproduzir exatamente). PyTorch com CUDA conforme o driver (`--index-url https://download.pytorch.org/whl/cu128` foi o usado).
- Pesos: `yolo26m.pt` (ultralytics baixa automaticamente; cópia em `projeto/pesos/`), `osnet_x1_0_msmt17.pt` (BoxMOT baixa automaticamente).
- Para Pipeline B gerenciado: credenciais AWS com Bedrock habilitado; endpoints em `clients.py` (`MANTLE`, `RUNTIME_OPENAI`). Para modelo próprio: vLLM com `Qwen/Qwen3-VL-8B-Instruct-FP8` (precisa de `ninja`), ver `scripts/cloud_qwen_job.sh`.

### 5.2 Preparar o vídeo
```bash
ffmpeg -v error -i entrada.mp4 -vf fps=5 -c:v libx264 -crf 18 video_5fps.mp4 -y
```
Toda a cadeia assume a sequência a 5 quadros/s (reamostragem por tempo, não por índice).

### 5.3 Pipeline A
```python
import sys; sys.path.insert(0, "src")
from retailcv.detect import detect_video, load_cache
from retailcv.track import track_video
from retailcv.postprocess import run_incremental
from retailcv.reid_gallery import run_reid

detect_video("video_5fps.mp4", "det.npz", model_name="yolo26m.pt", conf=0.25)      # GPU, uma vez
cache = load_cache("det.npz")
track_video("video_5fps.mp4", cache, "bytetrack", "out/E0.txt")                      # ou "hybridsort"
run_incremental("out/E0.txt", "out/E2")                                             # P0_raw … P4_stitch (CPU)
run_reid("video_5fps.mp4", "out/E2/P4_stitch.txt", "out/E3_reid.txt")               # visitantes únicos (GPU)
```
Métricas de negócio (ocupação, permanência, fluxo, mapa de calor) a partir do MOT + zonas: ver `scripts/prep_insights_data.py` (função `zone_of`) e `scripts/smoke_test.py`. Parâmetros pré-registrados das heurísticas: comprimento mínimo 5 quadros, confiança média 0,4, lacuna máxima 10 quadros, costura ≤ 25 quadros e ≤ 150 px.

### 5.4 Pipeline B
```python
from retailcv.pipeline_b.runner import run_model
run_model("video_5fps.mp4", "main", "anthropic.claude-haiku-4-5", fps=0.5, out_dir="b_out/haiku", workers=10)
```
IDs usados: `anthropic.claude-{haiku-4-5,sonnet-5,opus-5}`, `openai.gpt-5.6-{luna,terra,sol}`, `us.openai.gpt-6-astra`, `us.xai.grok-4.6`, `google.gemma-4-{26b-a4b,31b}`, `vllm:Qwen/Qwen3-VL-8B-Instruct-FP8`. `video_key` seleciona a descrição de zonas (`ref`, `main`; `scale` usa a de `main`). Vídeo nativo (Pegasus 1.2, clipes de 60 s via S3): `scripts/cloud_b3_job.sh`.

### 5.5 Avaliação
```bash
python scripts/eval_screening.py --gt data/gt_ref.txt --trackers-dir runs/screening --seq-len 1691   # TrackEval (venv numpy<1.24)
python scripts/eval_b1.py --gt data/gt_ref.txt --b1-dir data/b1/b1_out
python scripts/eval_sampling.py     # MAE/IC vs contagens humanas (respostas_main.json)
python scripts/eval_iho.py          # eventos pegar/devolver (±5 s, zona) e IoU de examinar
python scripts/make_report.py && python scripts/make_figures.py
```
Validação humana em vídeos sem verdade densa: `scripts/make_sampling_kit.py` gera clipes e HTML local; as respostas (JSON) alimentam `eval_sampling.py`.

### 5.6 Orquestração em nuvem (opcional)
Cada `scripts/cloud_*_job.sh` é um user-data EC2 completo: instala dependências, baixa vídeo e código do S3, executa, envia saídas e **termina a instância**. Para reutilizar: ajuste `BUCKET`, `REGION`, chaves dos vídeos e o perfil de instância (precisa de S3 e, para Pipeline B, `bedrock:InvokeModel*`). Imagens usadas: DLAMI Base GPU Ubuntu 24.04 (GPU) e Ubuntu 24.04 (CPU).

## 6. Decisões de método que valem para outros projetos
- Sequência oficial a 5 quadros/s por PTS; todos os artefatos referem-se a ela.
- Detecção em cache; rastreadores comparados sobre detecções idênticas.
- Critérios de avaliação definidos antes da execução (taxa de amostragem, parâmetros das heurísticas, bateria do agente, critério inclusivo de contagem).
- Verdade de referência: pré-anotação com variante diferente do detector avaliado (YOLO26x vs YOLO26m) para reduzir viés de confirmação; revisão humana integral no CVAT; eventos no BORIS.
- Validação por amostragem com IC 95 % bootstrap quando não há verdade densa.
- MAE e viés em vez de erro percentual (contagens frequentemente zero).

## 7. Privacidade e licença
Vídeos, quadros e qualquer artefato com imagens de pessoas ficam fora de repositórios públicos; publique apenas código, configurações e métricas. O bucket é privado; a transferência para o provedor de nuvem está documentada na monografia (Apêndice A). Licença do código: AGPL-3.0 (imposta por ultralytics e boxmot). O histórico completo das decisões está em `DECISOES.md` e `DIARIO.md` (kit `projeto/docs/`).
