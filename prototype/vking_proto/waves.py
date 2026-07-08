"""Wave trace builder for the prototype canvas (VCD step data)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from . import delta

_TIMESCALE_RE = re.compile(r"^\$timescale\s+(.+?)\s+\$end\s*$", re.MULTILINE)


def _read_timescale(path: Path) -> str:
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    except OSError:
        return "1ns"
    m = _TIMESCALE_RE.search(head)
    return m.group(1).strip() if m else "1ns"


def _signal_leaf(name: str) -> str:
    base = name.split(".")[-1]
    bracket = base.find("[")
    return base[:bracket].lower() if bracket >= 0 else base.lower()


def _default_signal_filter(name: str) -> bool:
    leaf = _signal_leaf(name)
    if leaf in ("clk", "clock") or leaf.endswith("_clk") or leaf.endswith("clk"):
        return True
    if leaf.startswith("rst") or leaf.startswith("reset"):
        return True
    if leaf.startswith("count") or "count" in leaf:
        return True
    if "out" in leaf:
        return True
    return False


def _matches_filter(name: str, signal_filter: list[str] | None) -> bool:
    if signal_filter is None:
        return _default_signal_filter(name)
    leaf = _signal_leaf(name)
    full = name.lower()
    for pattern in signal_filter:
        p = pattern.lower()
        if p in full or p == leaf or full.endswith("." + p):
            return True
    return False


def build_wave_traces(
    vcd_path: str | Path,
    signal_filter: list[str] | None = None,
    max_transitions: int = 400,
) -> dict[str, Any]:
    """Build per-signal step traces ``[{t, v}]`` with carried state for canvas rendering.

    Uses :func:`delta.parse_vcd` for value-change events. When *signal_filter* is
    ``None``, selects clk, rst*, count*, and *out* signals by heuristic.

    Returns ``{timescale, t_max, signals: [{name, values: [{t,v}]}]}``.
    """
    path = Path(vcd_path)
    parsed = delta.parse_vcd(path)
    if not parsed.events:
        return {
            "timescale": _read_timescale(path) if path.is_file() else "1ns",
            "t_max": 0,
            "signals": [],
            "message": parsed.reason or "no events parsed",
        }

    timescale = _read_timescale(path)
    selected_names = sorted(
        {e["signal"] for e in parsed.events if _matches_filter(e["signal"], signal_filter)}
    )

    signals_out: list[dict[str, Any]] = []
    t_max = 0
    budget = max_transitions

    for sig in selected_names:
        if budget <= 0:
            break
        values: list[dict[str, int | str]] = []
        last_v: str | None = None
        for event in sorted(parsed.events, key=lambda e: (e["time"], e["delta_idx"])):
            if event["signal"] != sig:
                continue
            t = event["time"]
            v = event["value"]
            if last_v is None or v != last_v:
                values.append({"t": t, "v": v})
                last_v = v
                t_max = max(t_max, t)
                budget -= 1
                if budget <= 0:
                    break
        if values:
            signals_out.append({"name": sig, "values": values})

    return {
        "timescale": timescale,
        "t_max": t_max,
        "signals": signals_out,
    }
