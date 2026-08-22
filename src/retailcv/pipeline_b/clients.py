"""Clientes unificados do Pipeline B — mesmo contrato para os 3 fornecedores (D10).

analyze_frame(jpeg_bytes) -> (dict conforme FRAME_SCHEMA, usage, wall_s)
- Claude:      Anthropic Messages API no bedrock-mantle, tool-use FORÇADO.
- GPT/Gemma:   OpenAI Responses API no bedrock-mantle, text.format json_schema.
Falhas de schema são registradas (dimensão complexidade) e recebem 1 retry.
"""
from __future__ import annotations

import base64
import json
import time

from .frame_schema import FRAME_SCHEMA

MANTLE = "https://bedrock-mantle.us-east-1.api.aws"


def _validate(d: dict) -> dict:
    assert isinstance(d.get("people_count"), int)
    assert isinstance(d.get("people"), list)
    return d


class ClaudeClient:
    def __init__(self, model_id: str, prompt: str, region: str = "us-east-1"):
        import boto3
        from anthropic import AnthropicBedrockMantle
        session = boto3.Session(region_name=region)
        creds = session.get_credentials().get_frozen_credentials()
        self.client = AnthropicBedrockMantle(
            aws_access_key=creds.access_key, aws_secret_key=creds.secret_key,
            aws_session_token=creds.token, aws_region=region)
        self.model_id, self.prompt = model_id, prompt

    def analyze_frame(self, jpeg: bytes):
        t0 = time.time()
        msg = self.client.messages.create(
            model=self.model_id, max_tokens=2048,
            tools=[{"name": "registrar_frame", "description": "Registra a análise do frame",
                    "input_schema": FRAME_SCHEMA}],
            tool_choice={"type": "tool", "name": "registrar_frame"},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                             "data": base64.standard_b64encode(jpeg).decode()}},
                {"type": "text", "text": self.prompt},
            ]}])
        out = _validate(next(b for b in msg.content if b.type == "tool_use").input)
        usage = {"input_tokens": msg.usage.input_tokens, "output_tokens": msg.usage.output_tokens}
        return out, usage, time.time() - t0


class OpenAICompatClient:
    """GPT-5.x e Gemma 4 via Responses API do mantle (bearer token SigV4)."""

    def __init__(self, model_id: str, prompt: str, region: str = "us-east-1"):
        import boto3
        from aws_bedrock_token_generator import BedrockTokenGenerator
        from openai import OpenAI
        session = boto3.Session(region_name=region)
        self._token_gen = BedrockTokenGenerator()
        self._session, self._region = session, region
        token = self._token_gen.get_token(session.get_credentials(), region)
        self.client = OpenAI(base_url=f"{MANTLE}/openai/v1", api_key=token)
        self.model_id, self.prompt = model_id, prompt

    def refresh_token(self):
        token = self._token_gen.get_token(self._session.get_credentials(), self._region)
        self.client.api_key = token

    def analyze_frame(self, jpeg: bytes):
        t0 = time.time()
        resp = self.client.responses.create(
            model=self.model_id, max_output_tokens=4096,
            input=[{"role": "user", "content": [
                {"type": "input_image",
                 "image_url": f"data:image/jpeg;base64,{base64.standard_b64encode(jpeg).decode()}"},
                {"type": "input_text", "text": self.prompt},
            ]}],
            text={"format": {"type": "json_schema", "name": "registrar_frame",
                             "schema": FRAME_SCHEMA, "strict": False}})
        out = _validate(json.loads(resp.output_text))
        u = resp.usage
        reasoning = getattr(getattr(u, "output_tokens_details", None), "reasoning_tokens", 0) or 0
        usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                 "reasoning_tokens": reasoning}
        return out, usage, time.time() - t0


def make_client(model_id: str, prompt: str):
    if model_id.startswith("anthropic."):
        return ClaudeClient(model_id, prompt)
    return OpenAICompatClient(model_id, prompt)
