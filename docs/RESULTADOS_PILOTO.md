# Piloto bedrock-mantle — 26/07/2026 (frame de teste: ref @ 60s, 1920×1080)

Frame com ~5-6 pessoas visíveis (contagem exata pendente do ground truth). Auth: SigV4/bearer token via perfil `automations` — sem necessidade de API key manual.

| Modelo | Via | people_count | Latência | Input tok | Output tok (reasoning) | JSON conforme schema? |
|---|---|---|---|---|---|---|
| claude-haiku-4-5 | Messages + tool forçado | 5 | 6,9s | 2.815 | 364 (—) | ✅ 1ª tentativa |
| claude-sonnet-5 | Messages + tool forçado | 4 | 11,6s | 3.919 | ~310 | ✅ 1ª tentativa |
| gpt-5.6-luna | Responses + json_schema | 5 | 10,9s | 2.593 | 655 (431 reasoning!) | ✅ 1ª tentativa |
| gemma-4-26b-a4b | Responses + json_schema | 3–4 | 6,9s | **725** | 121–156 (0) | ✅ 1ª tentativa |

## Descobertas que atualizam as estimativas do plano
1. **Structured output funciona em todos** — inclusive Gemma 4 via json_schema na Responses API. Zero retries no piloto.
2. **GPT-5.6 Luna: 66% do output é reasoning** (431/655) — custo de output real ~1,6× o estimado. Ainda assim segue barato (~$14-15 no vídeo principal vs $11,57 estimado).
3. **Sonnet 5 não inflou** neste caso (output ~310-315, thinking adaptativo não disparou em tarefa simples) e o input veio maior que o previsto (3.919 vs ~2.991 — overhead do tool schema).
4. **Gemma 4 usa pouquíssimos tokens de input (725)** → budget de imagem baixo por default; `detail: high` não mudou o input (725 igual) — investigar como elevar o budget de visão (pode explicar o undercount de 3-4 vs 5). Variação entre runs (3 vs 4 pessoas) também observada.
5. Haiku/GPT/Sonnet convergem em 4-5 pessoas com zonas plausíveis; divergências de contagem entre modelos já aparecem — exatamente o que o experimento vai medir contra o GT.
6. Latências 7-12s/frame em sequencial → 2.220 frames = 4-7 h se serial; **paralelizar (10-20 requests concorrentes) na implementação real**.

## Pendências técnicas
- Pegasus 1.2 (vídeo nativo) não testado ainda — requer clipe no S3 + InvokeModel; fazer no piloto do eixo B3.
- Confirmar parâmetro de token budget de visão do Gemma 4 no mantle.
- Claude Opus 5 não testado (mesma API do Sonnet — baixo risco); testar antes do run completo.
