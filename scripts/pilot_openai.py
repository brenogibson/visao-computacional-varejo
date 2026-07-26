"""Piloto 2: GPT-5.6 / Gemma 4 via bedrock-mantle (OpenAI Responses API).
Auth: bearer token de curta duração gerado por SigV4 (aws-bedrock-token-generator),
perfil automations. Valida: invocação, structured output json_schema, usage real."""
import json, sys, time, base64

import boto3
from aws_bedrock_token_generator import BedrockTokenGenerator
from openai import OpenAI
from schema_frame import FRAME_SCHEMA, PROMPT

MODEL = sys.argv[1] if len(sys.argv) > 1 else "openai.gpt-5.6-luna"

session = boto3.Session(profile_name="automations", region_name="us-east-1")
token = BedrockTokenGenerator().get_token(session.get_credentials(), "us-east-1")

client = OpenAI(
    base_url="https://bedrock-mantle.us-east-1.api.aws/openai/v1",
    api_key=token,
)

img_b64 = base64.standard_b64encode(open("frame_test.jpg", "rb").read()).decode()

t0 = time.time()
resp = client.responses.create(
    model=MODEL,
    max_output_tokens=4096,
    input=[{
        "role": "user",
        "content": [
            {"type": "input_image", "image_url": f"data:image/jpeg;base64,{img_b64}"},
            {"type": "input_text", "text": PROMPT},
        ],
    }],
    text={
        "format": {
            "type": "json_schema",
            "name": "registrar_frame",
            "schema": FRAME_SCHEMA,
            "strict": False,
        }
    },
)
dt = time.time() - t0

print(f"=== {MODEL} | {dt:.1f}s ===")
print(json.dumps(json.loads(resp.output_text), ensure_ascii=False, indent=1))
u = resp.usage
reasoning = getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", "n/a")
print(f"USAGE input={u.input_tokens} output={u.output_tokens} (reasoning={reasoning})")
