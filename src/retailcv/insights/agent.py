"""Etapa agêntica (§3.7): agente Claude com tool-use consulta as métricas de UM pipeline
e responde a bateria pré-registrada (D17). Sessões separadas por pipeline, mesmas perguntas.

Mede tokens e latência por pergunta (custo da etapa também é resultado).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

MODEL = "anthropic.claude-sonnet-5"

QUESTIONS = [
    "Qual zona da loja tem a maior ocupação total (pessoa-segundos) e qual a menor?",
    "Qual é a janela de 5 minutos com maior movimento no período gravado?",
    "Quantos visitantes únicos a loja recebeu no período?",
    "Qual zona converte mais passagem em interação com produto (razão interações/ocupação)?",
    "Em qual zona ocorrem mais devoluções de produto (demanda latente com barreira)?",
    "Há algum gargalo de circulação (zona com alta ocupação e baixa interação)?",
    "Qual o tempo médio de permanência na zona mesa_central por visita?",
    "A zona entrada tem fluxo constante ou concentrado em picos?",
    "Se a loja pudesse reposicionar UMA seção para aumentar interação, qual deveria ser e por quê?",
    "Resuma em 3 frases o comportamento típico do cliente neste período.",
]

SYSTEM = (
    "Você é um analista de dados de varejo. Responda a pergunta do lojista usando SOMENTE os "
    "dados disponíveis nas ferramentas. Se a métrica necessária estiver marcada como INDISPONÍVEL "
    "neste pipeline, diga isso explicitamente e responda com a melhor aproximação possível, "
    "deixando clara a limitação. Seja direto: 2-5 frases, com números."
)

TOOLS = [
    {"name": "info_dataset", "description": "Visão geral do dataset: pipeline, vídeo, zonas, ressalvas",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "ocupacao_por_zona", "description": "Pessoa-segundos por zona; visitantes únicos e permanência média por visita quando disponíveis",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "fluxo_temporal", "description": "Série por janelas de 5 min: média/pico de pessoas (e únicos, se disponível)",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "interacoes", "description": "Eventos/resumo de interação com produto por zona (se disponível)",
     "input_schema": {"type": "object", "properties": {}}},
]


def make_tool_handler(ds: dict):
    def handle(name: str, _args: dict) -> str:
        if name == "info_dataset":
            return json.dumps({k: ds[k] for k in ("pipeline", "video", "zonas") if k in ds}
                              | {"ressalvas": ds.get("ressalva_interacoes", "")}, ensure_ascii=False)
        if name == "ocupacao_por_zona":
            return json.dumps({k: ds[k] for k in (
                "ocupacao_por_zona_pessoa_segundos", "visitantes_unicos_total",
                "visitantes_unicos_por_zona", "permanencia_media_por_visita_s",
                "n_visitas_por_zona") if k in ds}, ensure_ascii=False)
        if name == "fluxo_temporal":
            return json.dumps(ds.get("fluxo_temporal_janelas_5min", []), ensure_ascii=False)
        if name == "interacoes":
            out = {k: ds[k] for k in ("interacoes_por_zona_resumo", "ressalva_interacoes",
                                      "interacoes_com_produto") if k in ds}
            return json.dumps(out or {"interacoes": "sem dados"}, ensure_ascii=False)
        return json.dumps({"erro": f"ferramenta desconhecida {name}"})
    return handle


def run_battery(dataset_path: str | Path, region: str = "us-east-1") -> dict:
    import boto3
    from anthropic import AnthropicBedrockMantle

    ds = json.loads(Path(dataset_path).read_text())
    handle = make_tool_handler(ds)
    session = boto3.Session(region_name=region)
    creds = session.get_credentials().get_frozen_credentials()
    client = AnthropicBedrockMantle(aws_access_key=creds.access_key, aws_secret_key=creds.secret_key,
                                    aws_session_token=creds.token, aws_region=region)

    answers = []
    for q in QUESTIONS:
        t0 = time.time()
        messages = [{"role": "user", "content": q}]
        tok_in = tok_out = 0
        tool_calls = 0
        for _turn in range(8):
            resp = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM,
                                          tools=TOOLS, messages=messages)
            tok_in += resp.usage.input_tokens
            tok_out += resp.usage.output_tokens
            if resp.stop_reason != "tool_use":
                final = "".join(b.text for b in resp.content if b.type == "text")
                break
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for b in resp.content:
                if b.type == "tool_use":
                    tool_calls += 1
                    results.append({"type": "tool_result", "tool_use_id": b.id,
                                    "content": handle(b.name, b.input)})
            messages.append({"role": "user", "content": results})
        else:
            final = "(limite de turnos atingido)"
        answers.append({"pergunta": q, "resposta": final.strip(), "tool_calls": tool_calls,
                        "input_tokens": tok_in, "output_tokens": tok_out,
                        "wall_s": round(time.time() - t0, 1)})
        print(f"[{ds['pipeline'][:10]}] Q: {q[:60]}... ({tool_calls} tools, {time.time()-t0:.0f}s)", flush=True)
    return {"pipeline": ds["pipeline"], "model": MODEL, "answers": answers,
            "total_input_tokens": sum(a["input_tokens"] for a in answers),
            "total_output_tokens": sum(a["output_tokens"] for a in answers)}
