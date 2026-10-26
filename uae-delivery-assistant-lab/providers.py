"""The two cloud adapters use the same instructions, retrieved evidence and schema."""
from __future__ import annotations

import os
import time
from importlib.metadata import version
from urllib.parse import urlparse

from delivery_assistant import DeliveryAnswer, SYSTEM_PROMPT, request_payload, validate_answer


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value or "YOUR-" in value or value.startswith("replace-"):
        raise ValueError(f"Fill {name} in .env before making this cloud call.")
    return value


def foundry_client():
    from openai import OpenAI
    base_url = required_env("AZURE_OPENAI_BASE_URL").rstrip("/") + "/"
    parsed = urlparse(base_url)
    if parsed.scheme != "https" or parsed.path != "/openai/v1/":
        raise ValueError("Use the HTTPS model inference base URL ending /openai/v1/.")
    key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
    if not key:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider
        key = get_bearer_token_provider(DefaultAzureCredential(), "https://ai.azure.com/.default")
    return OpenAI(base_url=base_url, api_key=key, timeout=30.0, max_retries=2)


def foundry_format() -> dict:
    return {"format": {"type": "json_schema", "name": "delivery_answer",
                       "schema": DeliveryAnswer.model_json_schema(), "strict": True}}


def finish_foundry(response, context: dict):
    if response.status != "completed" or not response.output_text:
        raise ValueError("Foundry returned an incomplete, refused or empty response. Review the run.")
    answer = validate_answer(response.output_text, context)
    usage = response.usage
    metadata = {
        "mode": "live", "logical_model_requests": 1,
        "model_requested": required_env("AZURE_OPENAI_DEPLOYMENT"),
        "model_returned": response.model, "response_id": response.id,
        "resource_region": os.getenv("AZURE_OPENAI_REGION", "not recorded"),
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "total_tokens": getattr(usage, "total_tokens", None),
        "sdk": f"openai {version('openai')}",
    }
    return answer, metadata


def call_foundry(context: dict, client=None):
    deployment = required_env("AZURE_OPENAI_DEPLOYMENT")
    own_client = client is None
    client = client or foundry_client()
    start = time.perf_counter()
    try:
        response = client.responses.create(
            model=deployment,
            instructions=SYSTEM_PROMPT,
            input=request_payload(context),
            text=foundry_format(),
            max_output_tokens=4096,
            store=False,
        )
        answer, metadata = finish_foundry(response, context)
        metadata["latency_ms"] = round((time.perf_counter() - start) * 1000, 1)
        return answer, metadata
    finally:
        if own_client:
            client.close()


def vertex_client():
    from google import genai
    from google.genai import types
    # Google's current Cloud SDK calls this enterprise=True (formerly vertexai=True).
    # This explicitly selects Google Cloud, not the Gemini Developer API.
    return genai.Client(
        enterprise=True,
        project=required_env("GOOGLE_CLOUD_PROJECT"),
        location=required_env("GOOGLE_CLOUD_LOCATION"),
        http_options=types.HttpOptions(api_version="v1", timeout=30_000,
                                     retry_options=types.HttpRetryOptions(attempts=3)),
    )


def vertex_config():
    from google.genai import types
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_json_schema=DeliveryAnswer.model_json_schema(),
        max_output_tokens=4096,
        automatic_continuation=False,
    )


def call_vertex(context: dict, client=None):
    model = required_env("VERTEX_MODEL")
    own_client = client is None
    client = client or vertex_client()
    start = time.perf_counter()
    try:
        response = client.models.generate_content(
            model=model, contents=request_payload(context), config=vertex_config()
        )
        candidates = response.candidates or []
        if not candidates or candidates[0].finish_reason != "STOP" or not response.text:
            raise ValueError("Google returned a blocked, incomplete or empty response. Review the run.")
        answer = validate_answer(response.text, context)
        usage = response.usage_metadata
        metadata = {
            "mode": "live", "logical_model_requests": 1,
            "model_requested": required_env("VERTEX_MODEL"),
            "model_returned": getattr(response, "model_version", None),
            "response_id": getattr(response, "response_id", None),
            "location": required_env("GOOGLE_CLOUD_LOCATION"),
            "input_tokens": getattr(usage, "prompt_token_count", None),
            "output_tokens": getattr(usage, "candidates_token_count", None),
            "reasoning_tokens": getattr(usage, "thoughts_token_count", None),
            "total_tokens": getattr(usage, "total_token_count", None),
            "latency_ms": round((time.perf_counter() - start) * 1000, 1),
            "sdk": f"google-genai {version('google-genai')}",
        }
        return answer, metadata
    finally:
        if own_client:
            client.close()
