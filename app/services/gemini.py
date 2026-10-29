import asyncio
import json
import logging

from app.core.config import get_settings
from app.services.scoring import fallback_explanation

logger = logging.getLogger(__name__)


async def generate_explanation(results: list[dict], missing_inputs: list[str]) -> tuple[str, str]:
    settings = get_settings()
    fallback = fallback_explanation(results, missing_inputs)
    if settings.gemini_api_key is None or not settings.gemini_api_key.get_secret_value().strip():
        return fallback, "fallback"
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        payload = {"results": results[:5], "missing_inputs": missing_inputs}
        prompt = (
            "Explain these crop recommendation results in plain language using only the supplied JSON facts. "
            "Do not change or recalculate rankings or scores. Do not invent yield, fertilizer, price, regional, "
            "weather or other agronomic facts. Explicitly say that results are advisory and crop profiles may "
            "be approximate. Keep the response under 120 words. JSON facts:\n" + json.dumps(payload, default=str)
        )
        response = await asyncio.wait_for(
            asyncio.to_thread(
                client.models.generate_content,
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=220),
            ),
            timeout=settings.gemini_timeout_seconds,
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text or len(text) > 1600:
            return fallback, "fallback"
        return text, "gemini"
    except Exception as exc:  # fallback is intentional for missing, unavailable or invalid AI responses
        logger.warning("Gemini explanation unavailable (%s)", type(exc).__name__)
        return fallback, "fallback"
