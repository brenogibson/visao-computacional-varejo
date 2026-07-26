"""Schema canônico de métricas comportamentais (v1).

Ambos os pipelines (A: CV tradicional; B: MLLM zero-shot) produzem estes objetos,
o que torna a comparação direta. Schema PLANO por decisão de projeto (DECISOES.md D10):
precisa funcionar no tool-use do Claude, no json_schema da Responses API e no xgrammar do vLLM.
"""
from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


class Action(str, Enum):
    CIRCULANDO = "circulando"
    PARADA_OLHANDO = "parada_olhando"
    EXAMINANDO_PRODUTO = "examinando_produto"
    PEGANDO_PRODUTO = "pegando_produto"
    DEVOLVENDO_PRODUTO = "devolvendo_produto"
    NO_CAIXA = "no_caixa"
    SENTADA = "sentada"


class PersonObservation(BaseModel):
    """Uma pessoa observada em um instante (frame)."""
    zone: str = Field(description="Nome lógico da zona (definido em configs/zones/*.json)")
    appearance: str = Field(default="", description="Descrição p/ matching entre frames (Pipeline B)")
    interacting_with_product: bool = False
    action: Action = Action.CIRCULANDO
    person_id: str | None = Field(default=None, description="ID pseudônimo (Pipeline A com tracker; None no B frame-a-frame)")
    bbox: tuple[float, float, float, float] | None = Field(default=None, description="x1,y1,x2,y2 (só Pipeline A)")


class FrameObservation(BaseModel):
    """Observação de um frame amostrado."""
    t_seconds: float = Field(description="Timestamp de apresentação (PTS) em segundos — nunca índice de frame")
    people_count: int
    people: list[PersonObservation]


class ZoneDwell(BaseModel):
    zone: str
    person_seconds: float = Field(description="Ocupação total (independente de identidade)")
    unique_visitors: int | None = Field(default=None, description="Requer identidade; None se indisponível")
    mean_dwell_per_person: float | None = None


class InteractionEvent(BaseModel):
    t_start: float
    t_end: float | None = None
    zone: str
    event_type: Action
    person_id: str | None = None


class VideoMetrics(BaseModel):
    """Artefato final por execução — comparável entre pipelines e contra o ground truth."""
    schema_version: str = SCHEMA_VERSION
    run_id: str
    video_id: str
    video_sha256: str
    pipeline: str = Field(description="'A' | 'B' | 'ground_truth'")
    config_ref: str = Field(description="Caminho do configs/runs/*.yaml que gerou este resultado")
    frames: list[FrameObservation]
    zone_dwell: list[ZoneDwell]
    interaction_events: list[InteractionEvent]
    total_unique_visitors: int | None = None
    heatmap_path: str | None = Field(default=None, description="PNG/NPY do mapa de calor (artefato separado)")
