from __future__ import annotations

import json
import re

from .. import config


class AIProviderError(RuntimeError):
    pass


def provider_name() -> str:
    return config.LLM_PROVIDER or "gemini"


def available() -> bool:
    if provider_name() == "openai":
        from .llmaas import openai_configured

        return openai_configured()
    return bool(config.GEMINI_API_KEY)


def complete_json(system: str, user: str) -> dict:
    if not available():
        raise AIProviderError(
            "No API key configured. Set GEMINI_API_KEY, OPENAI_API_KEY, or LLMaaS "
            "client credentials in .env and LLM_PROVIDER=gemini|openai."
        )
    try:
        if provider_name() == "openai":
            raw = _openai(system, user)
        else:
            raw = _gemini(system, user)
    except AIProviderError:
        raise
    except Exception as exc:
        raise AIProviderError(str(exc)) from exc
    return _parse_json(raw)


def complete_text(system: str, user: str) -> str:
    if not available():
        raise AIProviderError(
            "No API key configured. Set GEMINI_API_KEY, OPENAI_API_KEY, or LLMaaS credentials in .env."
        )
    try:
        if provider_name() == "openai":
            return _openai(system, user, json_mode=False)
        return _gemini(system, user, json_mode=False)
    except AIProviderError:
        raise
    except Exception as exc:
        raise AIProviderError(str(exc)) from exc


def _gemini(system: str, user: str, json_mode: bool = True) -> str:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise AIProviderError("google-genai is not installed") from exc
    client = genai.Client(api_key=config.GEMINI_API_KEY)
    cfg = types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.2,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    response = client.models.generate_content(
        model=config.GEMINI_MODEL,
        contents=user,
        config=cfg,
    )
    text = getattr(response, "text", None) or ""
    if not text:
        raise AIProviderError("Gemini returned an empty response")
    return text


def _openai(system: str, user: str, json_mode: bool = True) -> str:
    try:
        from .llmaas import init_openai_client, llmaas_configured
    except ImportError as exc:
        raise AIProviderError("openai client helper is not available") from exc
    client = init_openai_client()
    kwargs = {
        "model": config.OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "stream": False,
    }
    # Internal LLMaaS often rejects OpenAI json_object mode; the prompt still asks for JSON.
    if json_mode and not llmaas_configured():
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    text = response.choices[0].message.content or ""
    if not text:
        raise AIProviderError("OpenAI-compatible endpoint returned an empty response")
    return text


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
        return {"items": data}
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise AIProviderError("Model did not return JSON")
        data = json.loads(match.group(0))
        if isinstance(data, dict):
            return data
        return {"items": data}
