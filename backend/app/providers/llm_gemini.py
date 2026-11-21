import json
import re
from typing import Any

import httpx

from app.providers.base import (
    BaseLLMProvider,
    ProviderConfigurationError,
    ProviderExecutionError,
)


def extract_json_payload(text: str) -> dict[str, Any]:
    """Parse JSON from a model response, tolerating fenced markdown code blocks."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        return {"items": parsed}
    except json.JSONDecodeError as exc:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            parsed = json.loads(match.group(0))
            if isinstance(parsed, dict):
                return parsed
        raise ValueError("LLM response did not contain valid JSON.") from exc


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API provider using async HTTP requests."""

    provider_name = "gemini"
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
        *,
        timeout_seconds: int = 60,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model_name = model_name.strip()
        if not self.api_key:
            raise ProviderConfigurationError(
                "GEMINI_API_KEY is missing. Configure GEMINI_API_KEY in .env or switch "
                "LLM_PROVIDER=openai_compatible."
            )
        if not self.model_name:
            raise ProviderConfigurationError("GEMINI_MODEL must be specified.")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def _call_api(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        url = f"{self.BASE_URL}/{self.model_name}:generateContent"
        generation_config: dict[str, Any] = {
            "temperature": temperature,
            "maxOutputTokens": max_tokens,
        }
        if json_mode:
            generation_config["responseMimeType"] = "application/json"

        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": generation_config,
        }
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self.transport,
            ) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise ProviderExecutionError(
                f"Gemini API returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderExecutionError(f"Gemini API request failed: {exc}") from exc

        candidates = data.get("candidates") or []
        if not candidates:
            raise ProviderExecutionError("Gemini API returned no candidates.")
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(str(p.get("text", "")) for p in parts).strip()
        if not text:
            raise ProviderExecutionError("Gemini API returned empty text content.")
        return text

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> str:
        return await self._call_api(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False,
        )

    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        raw = await self._call_api(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        try:
            return extract_json_payload(raw)
        except ValueError as exc:
            raise ProviderExecutionError(f"Failed to parse JSON from Gemini: {exc}") from exc
