"""Schema JSON por frame do Pipeline B + prompts com as zonas APROVADAS pelo autor.

Schema PLANO (D10): portável entre tool-use do Claude, json_schema da Responses API
(GPT/Gemma) e xgrammar do vLLM. Zonas idênticas aos configs/zones/*.json — o MLLM
atribui a zona diretamente (não há bbox confiável para ponto-em-polígono no B).
"""

ZONES = ["entrada", "corredor_esquerdo", "corredor_central", "mesa_central",
         "corredor_direito", "caixa", "fora_de_zona"]

FRAME_SCHEMA = {
    "type": "object",
    "properties": {
        "people_count": {
            "type": "integer",
            "description": "Número total de pessoas visíveis no frame (inclua parcialmente ocluídas e ao fundo)",
        },
        "people": {
            "type": "array",
            "description": "Uma entrada por pessoa visível",
            "items": {
                "type": "object",
                "properties": {
                    "zone": {
                        "type": "string",
                        "enum": ZONES,
                        "description": "Zona onde os PÉS da pessoa tocam o chão",
                    },
                    "appearance": {
                        "type": "string",
                        "description": "Vestuário/aparência em poucas palavras (para reconhecer a pessoa em outros frames)",
                    },
                    "interacting_with_product": {
                        "type": "boolean",
                        "description": "True se está segurando/examinando/manuseando produto",
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

# Descrição das zonas por vídeo (layouts diferentes — D12). Critério: pés no chão.
ZONE_TEXT = {
    "ref": (
        "Zonas da loja (use o ponto onde os PÉS tocam o chão): "
        "'entrada' = porta ao fundo, no topo central da imagem; "
        "'corredor_esquerdo' = piso de ladrilhos à esquerda, ao longo das araras de lingerie (inclui o banco encostado na parede); "
        "'corredor_central' = faixa diagonal de piso que desce da entrada passando à DIREITA da mesa de promoções, até a parte inferior direita; "
        "'mesa_central' = junto à mesa retangular de promoções no centro-direita (pessoa mexendo em produtos sobre ela); "
        "'corredor_direito' = faixa estreita junto às gôndolas da direita, rumo ao canto superior direito; "
        "'caixa' = balcão de atendimento no canto superior direito; "
        "'fora_de_zona' = áreas de exposição sem circulação (ex.: canto inferior direito)."
    ),
    "main": (
        "Zonas da loja (use o ponto onde os PÉS tocam o chão): "
        "'entrada' = porta ao fundo, no topo central da imagem; "
        "'corredor_esquerdo' = piso de ladrilhos à esquerda, ao longo das araras de lingerie; "
        "'corredor_central' = faixa diagonal de piso que desce da entrada passando à DIREITA da mesa oval, até a parte inferior direita; "
        "'mesa_central' = junto à mesa OVAL branca de promoções no centro (pessoa mexendo em produtos sobre ela); "
        "'corredor_direito' = faixa estreita junto às gôndolas da direita, rumo ao canto superior direito; "
        "'caixa' = balcão de atendimento no canto superior direito; "
        "'fora_de_zona' = áreas de exposição sem circulação (ex.: canto inferior direito)."
    ),
}


def build_prompt(video_key: str) -> str:
    return (
        "Você é um sistema de análise de vídeo de varejo. Analise este frame de câmera de "
        "segurança de uma loja de vestuário e registre TODAS as pessoas visíveis, incluindo "
        "parcialmente ocluídas e pequenas ao fundo. A câmera está no alto, no fundo da loja, "
        "olhando para a entrada. " + ZONE_TEXT[video_key]
    )
