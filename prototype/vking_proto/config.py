"""Environment and AI provider configuration for the Vking prototype."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_PATH = _REPO_ROOT / ".env"

_OPENROUTER_DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct:free"
_GROQ_DEFAULT_MODEL = "llama-3.1-8b-instant"

_env_loaded = False


def load_env() -> Path | None:
    """Load repo-root ``.env`` via python-dotenv. Returns path if loaded."""
    global _env_loaded
    if _env_loaded:
        return _ENV_PATH if _ENV_PATH.is_file() else None
    try:
        from dotenv import load_dotenv
    except ImportError:
        return None
    if _ENV_PATH.is_file():
        load_dotenv(_ENV_PATH, override=False)
        _env_loaded = True
        return _ENV_PATH
    _env_loaded = True
    return None


def get_ai_config() -> dict[str, str] | None:
    """Return ``{provider, api_key, model}`` or ``None`` if no key is set.

    Priority: ``OPENROUTER_API_KEY`` then ``GROQ_API_KEY``.
    Never logs or prints key material.
    """
    load_env()

    openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if openrouter_key:
        model = (
            os.environ.get("OPENROUTER_MODEL", "").strip()
            or os.environ.get("AI_MODEL", "").strip()
            or _OPENROUTER_DEFAULT_MODEL
        )
        return {"provider": "openrouter", "api_key": openrouter_key, "model": model}

    groq_key = os.environ.get("GROQ_API_KEY", "").strip()
    if groq_key:
        model = (
            os.environ.get("GROQ_MODEL", "").strip()
            or os.environ.get("AI_MODEL", "").strip()
            or _GROQ_DEFAULT_MODEL
        )
        return {"provider": "groq", "api_key": groq_key, "model": model}

    return None


def ai_config_public(cfg: dict[str, Any] | None) -> dict[str, str] | None:
    """Strip secret fields from an AI config dict for API responses."""
    if not cfg:
        return None
    return {"provider": cfg["provider"], "model": cfg["model"]}
