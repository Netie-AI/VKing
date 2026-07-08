"""AI-assisted Verilog generation via OpenRouter or Groq (sync httpx)."""

from __future__ import annotations

import re
from typing import Any

import httpx

from .config import get_ai_config

_SYSTEM_PROMPT = (
    "You are a Verilog assistant for the Vking hardware workbench. "
    "Emit Profile A V2005-safe Verilog only: no SystemVerilog assertions (SVA), "
    "no classes/interfaces, no automatic variables in procedural blocks beyond "
    "integer/real where needed. Prefer clk/rst smoke-test style when generating "
    "testbenches: clock generator, reset sequence, simple self-checks with "
    "$display markers (VKING_RESULT: PASS/FAIL). Return raw Verilog only unless "
    "asked otherwise — no markdown prose."
)

_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?", re.MULTILINE)
_TRAILING_FENCE_RE = re.compile(r"\n?```\s*$")

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    text = _FENCE_RE.sub("", text, count=1)
    text = _TRAILING_FENCE_RE.sub("", text)
    return text.strip()


def _user_message(source: str | None, prompt: str | None, mode: str) -> str:
    mode = (mode or "generate").lower()
    if mode == "generate":
        return prompt or "Generate a small V2005-safe Verilog counter module with clk and rst_n."
    if mode == "improve":
        return (
            "Improve or fix the following Verilog module. Preserve ports and intent; "
            "return the full revised module only.\n\n"
            f"{source or ''}"
        )
    if mode == "tb":
        return (
            "Generate a Profile A V2005-safe testbench (clk/rst smoke style) for this DUT. "
            "Include $dumpfile/$dumpvars for waves.vcd and VKING_RESULT markers. "
            "Return the testbench Verilog module only.\n\n"
            f"{source or ''}"
        )
    raise ValueError(f"unknown mode: {mode!r}")


def _chat_completion(cfg: dict[str, str], user: str) -> str:
    provider = cfg["provider"]
    api_key = cfg["api_key"]
    model = cfg["model"]

    if provider == "openrouter":
        url = _OPENROUTER_URL
        headers = {
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://github.com/Netie-AI/VKing",
            "X-Title": "Vking Prototype",
        }
    elif provider == "groq":
        url = _GROQ_URL
        headers = {"Authorization": f"Bearer {api_key}"}
    else:
        raise ValueError(f"unsupported provider: {provider!r}")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("AI response contained no choices")
    content = choices[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("AI response contained empty content")
    return _strip_markdown_fences(content)


def generate_verilog(
    source: str,
    prompt: str | None = None,
    mode: str = "generate",
) -> dict[str, Any]:
    """Call configured AI provider and return generated Verilog metadata.

    ``mode``: ``generate`` (from prompt), ``improve`` (fix/enhance *source*),
    ``tb`` (testbench Verilog only).

    Never includes ``api_key`` in the returned dict.
    """
    cfg = get_ai_config()
    if not cfg:
        return {"ok": False, "error": "no AI API key configured", "verilog": None}

    try:
        user = _user_message(source, prompt, mode)
        verilog = _chat_completion(cfg, user)
    except httpx.HTTPStatusError as exc:
        return {
            "ok": False,
            "error": f"AI HTTP {exc.response.status_code}",
            "verilog": None,
            "provider": cfg["provider"],
            "model": cfg["model"],
        }
    except Exception as exc:  # noqa: BLE001 — surface provider errors to API layer
        return {
            "ok": False,
            "error": str(exc),
            "verilog": None,
            "provider": cfg["provider"],
            "model": cfg["model"],
        }

    return {
        "ok": True,
        "verilog": verilog,
        "provider": cfg["provider"],
        "model": cfg["model"],
        "mode": mode,
    }
