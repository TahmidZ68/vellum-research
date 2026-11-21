from typing import Any

import httpx

from app.providers.base import (
    BaseLLMProvider,
    ProviderConfigurationError,
    ProviderExecutionError,
)
from app.providers.llm_gemini import extract_json_payload


class OpenAICompatibleProvider(BaseLLMProvider):
    """OpenAI and OpenAI-compatible Chat Completions provider."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        *,
        timeout_seconds: int = 60,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model_name = model_name.strip()
        self.base_url = base_url.rstrip("/")
        if not self.api_key:
            raise ProviderConfigurationError(
                "OPENAI_API_KEY is missing. Configure OPENAI_API_KEY in .env to use "
                "the OpenAI-compatible provider."
            )
        if not self.model_name:
            raise ProviderConfigurationError("OPENAI_MODEL must be specified.")
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
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

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
                f"OpenAI-compatible API returned HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderExecutionError(
                f"OpenAI-compatible API request failed: {exc}"
            ) from exc

        choices = data.get("choices") or []
        if not choices:
            raise ProviderExecutionError("OpenAI-compatible API returned no choices.")
        content = str(choices[0].get("message", {}).get("content") or "").strip()
        if not content:
            raise ProviderExecutionError("OpenAI-compatible API returned empty content.")
        return content

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
            raise ProviderExecutionError(
                f"Failed to parse JSON from OpenAI-compatible provider: {exc}"
            ) from exc
