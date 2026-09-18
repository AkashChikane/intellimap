#!/usr/bin/env python3
"""Smoke-test the configured OpenAI-compatible / VW LLMaaS endpoint.

Loads credentials from the repo-root .env (never hard-code secrets).

  backend/.venv/bin/python backend/test_llm.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app import config  # noqa: E402
from app.ai.llmaas import init_openai_client, list_models, llmaas_configured  # noqa: E402
from app.ai.provider import AIProviderError  # noqa: E402


def main() -> int:
    print("LLM_PROVIDER     ", config.LLM_PROVIDER)
    print("OPENAI_BASE_URL  ", config.OPENAI_BASE_URL)
    print("OPENAI_MODEL     ", config.OPENAI_MODEL)
    print("LLMaaS configured", llmaas_configured())
    print("token URL        ", config.LLMAAS_TOKEN_URL)
    print()

    print("Creating client…")
    try:
        client = init_openai_client()
    except AIProviderError as exc:
        print(f"Failed to create client: {exc}")
        print("Check LLMAAS_TOKEN_URL (realm), LLMAAS_CLIENT_ID, and LLMAAS_CLIENT_SECRET in .env.")
        return 1
    print(client)
    print()

    print("Supported models:")
    try:
        models = list_models()
        if not models:
            print("  (none returned)")
        for mid in models:
            print(f"  - {mid}")
    except Exception as exc:
        print(f"  Could not list models: {exc}")
    print()

    print('Sending "Hi"…')
    completion = client.chat.completions.create(
        model=config.OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a concise assistant. When the user greets you, "
                    "reply with a short, warm greeting."
                ),
            },
            {"role": "user", "content": "Hi"},
        ],
        stream=False,
        temperature=0.0,
    )
    message = completion.choices[0].message
    print("role   ", message.role)
    print("answer ")
    print(message.content or "(empty)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
