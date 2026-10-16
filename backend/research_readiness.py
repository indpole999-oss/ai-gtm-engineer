"""Read-only model checks. Never generate output or enable a provider."""
import os
import httpx
from backend.hosted_model import groq_configured


def hosted_ai_enabled():
    return os.environ.get("GTM_HOSTED_AI_ENABLED", "false").strip().lower() == "true"


async def model_readiness():
    if groq_configured():
        enabled = hosted_ai_enabled()
        return {"provider": "groq", "state": "configured_unverified" if enabled else "paused", "can_attempt": enabled,
                "message": "Hosted AI is configured but has not been verified by this check." if enabled else
                "Hosted AI is paused. Research and qualification require explicit operator authorization before enabling it."}
    model = os.environ.get("GTM_LOCAL_MODEL", "qwen3:4b")
    url = os.environ.get("GTM_LOCAL_MODEL_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3, follow_redirects=False) as client:
            response = await client.get(url + "/api/tags")
            response.raise_for_status()
            names = {item["name"] for item in response.json()["models"]}
        available = model in names or (":" not in model and model + ":latest" in names)
        return {"provider": "ollama", "state": "model_available" if available else "model_missing", "can_attempt": available,
                "message": "Local model is listed. Valid research output still requires execution and evidence validation." if available else
                "The configured local model is not installed on the API/worker host. Research cannot run."}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"provider": "ollama", "state": "unavailable", "can_attempt": False,
                "message": "The local model service is unavailable from the API host. Configure a reachable Ollama service and model before research can run."}
