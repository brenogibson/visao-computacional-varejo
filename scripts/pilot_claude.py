"""Piloto 1: Claude Haiku 4.5 via bedrock-mantle (Messages API, SigV4 com perfil automations).
Valida: auth, invocação, tool-use forçado com o schema canônico, usage real."""
import json, sys, time, base64

import boto3
from anthropic import AnthropicBedrockMantle
from schema_frame import FRAME_SCHEMA, PROMPT

MODEL = sys.argv[1] if len(sys.argv) > 1 else "anthropic.claude-haiku-4-5"

session = boto3.Session(profile_name="automations", region_name="us-east-1")
creds = session.get_credentials().get_frozen_credentials()
client = AnthropicBedrockMantle(
    aws_access_key=creds.access_key,
    aws_secret_key=creds.secret_key,
    aws_session_token=creds.token,
    aws_region="us-east-1",
)

img_b64 = base64.standard_b64encode(open("frame_test.jpg", "rb").read()).decode()

t0 = time.time()
msg = client.messages.create(
    model=MODEL,
    max_tokens=2048,
    tools=[{
        "name": "registrar_frame",
        "description": "Registra a análise estruturada do frame",
        "input_schema": FRAME_SCHEMA,
    }],
    tool_choice={"type": "tool", "name": "registrar_frame"},
    messages=[{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
            {"type": "text", "text": PROMPT},
        ],
    }],
)
dt = time.time() - t0

tool_use = next(b for b in msg.content if b.type == "tool_use")
print(f"=== {MODEL} | {dt:.1f}s ===")
print(json.dumps(tool_use.input, ensure_ascii=False, indent=1))
u = msg.usage
print(f"USAGE input={u.input_tokens} output={u.output_tokens}")
