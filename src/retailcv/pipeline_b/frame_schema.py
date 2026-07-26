"""Schema canônico por frame (v0 do piloto) — PLANO de propósito (D10):
compatível com tool-use do Claude, json_schema da Responses API e xgrammar do vLLM."""

FRAME_SCHEMA = {
    "type": "object",
    "properties": {
        "people_count": {
            "type": "integer",
            "description": "Número total de pessoas visíveis no frame (clientes e funcionários)",
        },
        "people": {
            "type": "array",
            "description": "Uma entrada por pessoa visível",
            "items": {
                "type": "object",
                "properties": {
                    "zone": {
                        "type": "string",
                        "enum": [
                            "entrada", "corredor_central", "mesa_central",
                            "parede_esquerda", "parede_direita", "fundo_loja", "caixa",
                        ],
                        "description": "Zona da loja onde a pessoa está (pelo ponto onde os pés tocam o chão)",
                    },
                    "appearance": {
                        "type": "string",
                        "description": "Descrição curta de vestuário/aparência para matching entre frames (ex.: 'camiseta vermelha, calça jeans')",
                    },
                    "interacting_with_product": {
                        "type": "boolean",
                        "description": "True se a pessoa está segurando/examinando/manuseando um produto",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["circulando", "parada_olhando", "examinando_produto",
                                 "pegando_produto", "devolvendo_produto", "no_caixa", "sentada"],
                    },
                },
                "required": ["zone", "appearance", "interacting_with_product", "action"],
            },
        },
    },
    "required": ["people_count", "people"],
}

PROMPT = (
    "Você é um sistema de análise de vídeo de varejo. Analise este frame de câmera de "
    "segurança de uma loja de vestuário e registre TODAS as pessoas visíveis (incluindo "
    "parcialmente ocluídas ou ao fundo). A câmera está no alto, ao fundo da loja, olhando "
    "para a entrada. Zonas: 'entrada' (porta ao fundo), 'corredor_central' (piso claro central), "
    "'mesa_central' (mesa de produtos no centro-direita), 'parede_esquerda' (araras/prateleiras à esquerda), "
    "'parede_direita' (araras à direita), 'fundo_loja' (área próxima à câmera), 'caixa' (balcão). "
    "Use o ponto onde os pés tocam o chão para decidir a zona."
)
