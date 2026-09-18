from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "backend"
STORAGE = BACKEND / "storage"
DATA = ROOT / "data"
DB_PATH = STORAGE / "intellimap.db"
SAMPLE_XLSX = DATA / "IntelliMap_Architecture_Landscape.xlsx"

load_dotenv(ROOT / ".env")

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
LLMAAS_CLIENT_ID = os.getenv("LLMAAS_CLIENT_ID", "").strip()
LLMAAS_CLIENT_SECRET = os.getenv("LLMAAS_CLIENT_SECRET", "").strip()
LLMAAS_TOKEN_URL = os.getenv(
    "LLMAAS_TOKEN_URL",
    "https://idp.cloud.vwgroup.com/auth/realms/kums-fa/protocol/openid-connect/token",
).strip()
LLMAAS_API_CLIENT_ID = os.getenv("LLMAAS_API_CLIENT_ID", "").strip()
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

SENSITIVE_CLASSIFICATIONS = {"confidential", "pii", "pci"}
