"""Shared structured-output transport for the configured Groq provider."""
import json
import os
import logging
import time

import httpx


class HostedAIPaused(ValueError):
    pass


def groq_configured():
    return bool(os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ-API-KEY"))


def strict_schema(output_type):
    # Groq strict mode requires every property, including nullable/defaulted
    # fields. Keep application validators authoritative after decoding.
    schema = output_type.model_json_schema()

    def visit(node):
        if isinstance(node, dict):
            node.pop("default", None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(schema)
    return schema


async def groq_output(output_type, name, system_prompt, context):
    # A configured key does not authorize paid or unattended model execution.
    if os.environ.get("GTM_HOSTED_AI_ENABLED", "false").strip().lower() != "true":
        raise HostedAIPaused("Hosted AI execution is paused")
    api_key = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ-API-KEY", "")
    if not api_key:
        raise ValueError("Hosted model is not configured")
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    base_url = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
    logger = logging.getLogger(__name__)
    started = time.monotonic()
    logger.info("groq_request_started " + json.dumps({"model": model, "schema": name}))
    async with httpx.AsyncClient(timeout=90, follow_redirects=False) as client:
        response = await client.post(
            base_url + "/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model, "temperature": 0,
                "messages": [{"role": "system", "content": system_prompt},
                             {"role": "user", "content": json.dumps(context)}],
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": name, "strict": True, "schema": strict_schema(output_type)}},
            },
        )
        logger.info("groq_request_result " + json.dumps({"model": model, "schema": name,
            "http_status": response.status_code, "duration_ms": round((time.monotonic() - started) * 1000),
            "request_id": response.headers.get("x-request-id")}))
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            usage = payload.get("usage")
            usage = usage if isinstance(usage, dict) else {}
            logger.info("groq_response_metadata " + json.dumps({"model": payload.get("model", model),
                "schema": name, "usage": {k: v for k, v in usage.items() if k in
                    ("prompt_tokens", "completion_tokens", "total_tokens") and isinstance(v, int)}}))
        choices = payload.get("choices") if isinstance(payload, dict) else None
        if not isinstance(choices, list) or not choices:
            raise ValueError("Hosted model returned no output")
        content = choices[0]["message"]["content"]
        return output_type.model_validate_json(content), f"groq:{model}"[:100]
