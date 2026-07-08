"""Environment and AI provider configuration for the Vking prototype."""

from __future__ import annotations

import json
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


def _openrouter_config(model_override: str | None = None) -> dict[str, str] | None:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    model = (
        model_override
        or os.environ.get("OPENROUTER_MODEL", "").strip()
        or os.environ.get("AI_MODEL", "").strip()
        or _OPENROUTER_DEFAULT_MODEL
    )
    return {"provider": "openrouter", "api_key": key, "model": model}


def _groq_config(model_override: str | None = None) -> dict[str, str] | None:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return None
    model = (
        model_override
        or os.environ.get("GROQ_MODEL", "").strip()
        or os.environ.get("AI_MODEL", "").strip()
        or _GROQ_DEFAULT_MODEL
    )
    return {"provider": "groq", "api_key": key, "model": model}


def get_ai_config(
    *,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, str] | None:
    """Return ``{provider, api_key, model}`` or ``None`` if no key is set.

    Priority when *provider* is unset: OpenRouter then Groq.
    """
    load_env()
    provider = (provider or "").strip().lower() or None
    model = (model or "").strip() or None

    if provider == "openrouter":
        return _openrouter_config(model)
    if provider == "groq":
        return _groq_config(model)

    cfg = _openrouter_config(model)
    if cfg:
        return cfg
    return _groq_config(model)


def benchmark_models() -> list[dict[str, str]]:
    """Models to benchmark from ``VKING_BENCHMARK_MODELS`` JSON env or defaults."""
    load_env()
    raw = os.environ.get("VKING_BENCHMARK_MODELS", "").strip()
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                out: list[dict[str, str]] = []
                for item in data:
                    if isinstance(item, dict) and item.get("provider") and item.get("model"):
                        out.append(
                            {
                                "provider": str(item["provider"]),
                                "model": str(item["model"]),
                            }
                        )
                if out:
                    return out
        except json.JSONDecodeError:
            pass

    models: list[dict[str, str]] = []
    if os.environ.get("GROQ_API_KEY", "").strip():
        models.append({"provider": "groq", "model": os.environ.get("GROQ_MODEL", "").strip() or _GROQ_DEFAULT_MODEL})
    if os.environ.get("OPENROUTER_API_KEY", "").strip():
        models.append(
            {
                "provider": "openrouter",
                "model": os.environ.get("OPENROUTER_MODEL", "").strip() or _OPENROUTER_DEFAULT_MODEL,
            }
        )
    return models


def ai_config_public(cfg: dict[str, Any] | None) -> dict[str, str] | None:
    """Strip secret fields from an AI config dict for API responses."""
    if not cfg:
        return None
    return {"provider": cfg["provider"], "model": cfg["model"]}
