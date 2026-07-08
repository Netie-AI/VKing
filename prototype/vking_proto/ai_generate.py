"""AI-assisted Verilog generation via OpenRouter or Groq (sync httpx)."""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from .config import get_ai_config

_SYSTEM_PROMPT = """You are a Verilog engineer for the Vking hardware workbench.

Rules (non-negotiable):
- Profile A V2005-safe Verilog only: no SystemVerilog classes/interfaces/SVA.
- Every file starts with `timescale 1ns/1ps`.
- Testbenches must include: clock generator, reset sequence, $dumpfile("waves.vcd"), $dumpvars(0, tb_top).
- End sim with $display("VKING_RESULT: PASS") or $display("VKING_RESULT: FAIL") before $finish.
- Testbenches MUST be named module tb_top (iverilog -s tb_top).
- Use explicit bit widths in literals (8'd0, 8'hFF) — never WIDTH'b... or PARAM'b...
- Use negedge async reset when DUT uses rst_n.

Output contract:
- Return ONLY raw Verilog source. No markdown fences, no prose, no JSON.
- One complete module per response."""

_TB_PROMPT_TEMPLATE = """Generate a self-checking testbench module for this DUT.

Checklist (verify mentally before answering):
1. module tb_top — exact name required
2. `timescale 1ns/1ps` at top
3. Declare all wires/regs — DUT outputs are wire, never assign to them in TB
4. Instantiate DUT with exact port names/widths
5. Clock + reset sequence
6. $dumpfile("waves.vcd") and $dumpvars(0, tb_top)
7. Self-check with $display("VKING_RESULT: PASS") or FAIL using decimal literals
8. $finish after checks

DUT source:
{source}"""

_IMPROVE_PROMPT = """Fix or improve this Verilog. Preserve ports and intent.
Return the full revised module only (raw Verilog, no markdown).

{source}"""

_GENERATE_PROMPT = """{prompt}

Return one V2005-safe Verilog module with clk and rst_n. Raw Verilog only."""

_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?", re.MULTILINE)
_TRAILING_FENCE_RE = re.compile(r"\n?```\s*$")
_MODULE_RE = re.compile(r"\bmodule\s+(\w+)", re.I)
_TIMESCALE_RE = re.compile(r"`timescale\s+\S+", re.I)
_DUMPFILE_RE = re.compile(r"\$dumpfile\s*\(", re.I)
_DUMPVARS_RE = re.compile(r"\$dumpvars\s*\(", re.I)
_VKING_RESULT_RE = re.compile(r"VKING_RESULT\s*:\s*(PASS|FAIL)", re.I)

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def _normalize_tb_module(verilog: str, top: str = "tb_top") -> str:
    """Rename first module to expected TB top if model used wrong name."""
    m = _MODULE_RE.search(verilog)
    if m and m.group(1) != top:
        return _MODULE_RE.sub(f"module {top}", verilog, count=1)
    return verilog


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    text = _FENCE_RE.sub("", text, count=1)
    text = _TRAILING_FENCE_RE.sub("", text)
    return text.strip()


def verify_verilog(source: str, *, mode: str = "tb") -> dict[str, Any]:
    """Static verifier before compile — returns {ok, errors, warnings}."""
    errors: list[str] = []
    warnings: list[str] = []
    text = (source or "").strip()
    if not text:
        errors.append("empty output")
        return {"ok": False, "errors": errors, "warnings": warnings}

    if not _MODULE_RE.search(text):
        errors.append("missing module declaration")
    if not _TIMESCALE_RE.search(text):
        errors.append("missing `timescale")
    if "```" in text:
        errors.append("markdown fences present — raw Verilog only")

    if mode == "tb":
        if not re.search(r"\bmodule\s+tb_top\b", text, re.I):
            errors.append("testbench module must be named tb_top")
        if not _DUMPFILE_RE.search(text):
            errors.append("missing $dumpfile")
        if not _DUMPVARS_RE.search(text):
            errors.append("missing $dumpvars")
        if not _VKING_RESULT_RE.search(text):
            warnings.append("missing VKING_RESULT marker")

    return {"ok": not errors, "errors": errors, "warnings": warnings}


def _user_message(source: str | None, prompt: str | None, mode: str) -> str:
    mode = (mode or "generate").lower()
    if mode == "generate":
        user_prompt = prompt or "Generate a small 8-bit counter with clk, rst_n, en."
        return _GENERATE_PROMPT.format(prompt=user_prompt)
    if mode == "improve":
        return _IMPROVE_PROMPT.format(source=source or "")
    if mode == "tb":
        return _TB_PROMPT_TEMPLATE.format(source=source or "")
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
        "temperature": 0.1,
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
    *,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Call configured AI provider and return generated Verilog metadata."""
    cfg = get_ai_config(provider=provider, model=model)
    if not cfg:
        return {"ok": False, "error": "no AI API key configured", "verilog": None}

    t0 = time.perf_counter()
    try:
        user = _user_message(source, prompt, mode)
        verilog = _chat_completion(cfg, user)
        if mode == "tb":
            verilog = _normalize_tb_module(verilog)
        verify = verify_verilog(verilog, mode=mode if mode in ("tb", "generate", "improve") else "tb")
    except httpx.HTTPStatusError as exc:
        return {
            "ok": False,
            "error": f"AI HTTP {exc.response.status_code}",
            "verilog": None,
            "provider": cfg["provider"],
            "model": cfg["model"],
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": str(exc),
            "verilog": None,
            "provider": cfg["provider"],
            "model": cfg["model"],
            "latency_ms": int((time.perf_counter() - t0) * 1000),
        }

    return {
        "ok": True,
        "verilog": verilog,
        "provider": cfg["provider"],
        "model": cfg["model"],
        "mode": mode,
        "verify": verify,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }
