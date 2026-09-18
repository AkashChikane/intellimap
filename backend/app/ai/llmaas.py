from __future__ import annotations

import threading
import time

import httpx
from openai import OpenAI

from .. import config

_lock = threading.Lock()
_cached_token = ""
_cached_until = 0.0


def llmaas_configured() -> bool:
    return bool(config.LLMAAS_CLIENT_ID and config.LLMAAS_CLIENT_SECRET and config.LLMAAS_TOKEN_URL)


def openai_configured() -> bool:
    return llmaas_configured() or bool(config.OPENAI_API_KEY)


def get_token() -> str:
    global _cached_token, _cached_until
    now = time.time()
    with _lock:
        if _cached_token and now < _cached_until:
            return _cached_token
        if not llmaas_configured():
            from .provider import AIProviderError

            raise AIProviderError(
                "LLMaaS is not configured. Set LLMAAS_CLIENT_ID, LLMAAS_CLIENT_SECRET, "
                "and LLMAAS_TOKEN_URL in .env."
            )
        try:
            response = httpx.post(
                config.LLMAAS_TOKEN_URL,
                data={
                    "client_id": config.LLMAAS_CLIENT_ID,
                    "client_secret": config.LLMAAS_CLIENT_SECRET,
                    "grant_type": "client_credentials",
                },
                timeout=30.0,
            )
        except httpx.HTTPError as exc:
            from .provider import AIProviderError

            raise AIProviderError(f"Cloud IDP request failed: {exc}") from exc
        if response.status_code != 200:
            from .provider import AIProviderError

            raise AIProviderError(
                f"Error from Cloud IDP: {response.status_code} - {response.text}"
            )
        payload = response.json()
        token = payload.get("access_token") or ""
        if not token:
            from .provider import AIProviderError

            raise AIProviderError("Cloud IDP did not return access_token")
        expires_in = int(payload.get("expires_in") or 300)
        _cached_token = token
        _cached_until = now + max(expires_in - 30, 30)
        return token


def init_openai_client() -> OpenAI:
    if llmaas_configured():
        headers = {}
        if config.LLMAAS_API_CLIENT_ID:
            headers["X-LLM-API-CLIENT-ID"] = f"Bearer {config.LLMAAS_API_CLIENT_ID}"
        return OpenAI(
            api_key=get_token(),
            base_url=config.OPENAI_BASE_URL,
            default_headers=headers or None,
        )
    if not config.OPENAI_API_KEY:
        from .provider import AIProviderError

        raise AIProviderError("Set OPENAI_API_KEY in .env, or configure LLMaaS client credentials.")
    return OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)


def list_models() -> list[str]:
    client = init_openai_client()
    page = client.models.list()
    ids = []
    for model in page.data:
        mid = getattr(model, "id", None)
        if mid:
            ids.append(mid)
    return sorted(ids)
