"""Reconstructed delta layer (PROTOTYPE).

This module does **not** implement Stage-2 VPI scheduler hooks. Delta indices
are **inferred** from VCD value-change order within the same simulation
timestamp — a file-order proxy, not true IEEE 1364 delta cycles.

**tbgen recommendation:** emit both ``.fst`` (GTKWave via ``vvp -fst``) and
``.vcd`` (delta reconstruction panel). Master-plan v0.1 codegen currently
targets FST only; until ``tbgen`` is updated, add a second ``$dumpfile`` block
(see ``vcd_writer.verilog_dual_dump_blocks``) or run a VCD dump pass.

**Limitations (honest prototype scope):**
- VCD only; ``.fst`` returns empty events with a deferred reason.
- Delta order = VCD dump order at equal ``#time``, not simulator delta cycles.
- Scalar and binary-vector values (``0/1/x/z``); reals and string vars skipped.
- No ``$dumpoff``/``$dumpon`` filtering; collapsed scopes not expanded.
- Multi-dimensional arrays and escaped identifiers: best-effort name capture.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict


class DeltaEvent(TypedDict):
    time: int
    delta_idx: int
    signal: str
    value: str


@dataclass(frozen=True)
class VcdParseResult:
    """Outcome of :func:`parse_vcd`."""

    events: list[DeltaEvent]
    reason: str = ""

    def __bool__(self) -> bool:
        return bool(self.events)


_FST_DEFERRED = "FST parse deferred; convert or use VCD for delta view"

_VAR_RE = re.compile(
    r"^\$var\s+(\S+)\s+(\d+)\s+(\S+)\s+(.+?)\s+\$end\s*$"
)
_SCOPE_RE = re.compile(r"^\$scope\s+(\S+)\s+(.+?)\s+\$end\s*$")
_TIME_RE = re.compile(r"^#(\d+)")
_SCALAR_RE = re.compile(r"^([01xXzZ])(\S+)$")
_VECTOR_RE = re.compile(r"^[bB]([01xXzZ]+)\s+(\S+)$")
_REAL_RE = re.compile(r"^[rR](\S+)\s+(\S+)$")


def _normalize_value(raw: str) -> str:
    return raw.lower()


def _split_ref_tail(ref_tail: str) -> tuple[str, str]:
    """Return (signal_name, optional_range_suffix)."""
    ref_tail = ref_tail.strip()
    range_m = re.search(r"\s+(\[[^\]]+\])\s*$", ref_tail)
    if range_m:
        name = ref_tail[: range_m.start()].strip()
        return name, range_m.group(1)
    return ref_tail, ""


def _hier_name(scope_stack: list[str], ref: str, range_suffix: str) -> str:
    parts = [*scope_stack, ref]
    name = ".".join(p for p in parts if p)
    return f"{name}{range_suffix}" if range_suffix else name


def parse_var_line(line: str) -> tuple[str, str, str, str] | None:
    """Parse a ``$var`` line into (id, ref_name, range_suffix, size)."""
    m = _VAR_RE.match(line.strip())
    if not m:
        return None
    _vtype, size, var_id, ref_tail = m.groups()
    ref, range_suffix = _split_ref_tail(ref_tail)
    return var_id, ref, range_suffix, size


def parse_value_line(line: str) -> tuple[str, str] | None:
    """Parse a value-change line into (var_id, normalized_value)."""
    stripped = line.strip()
    if not stripped or stripped.startswith("$"):
        return None

    m = _SCALAR_RE.match(stripped)
    if m:
        return m.group(2), _normalize_value(m.group(1))

    m = _VECTOR_RE.match(stripped)
    if m:
        return m.group(2), _normalize_value(m.group(1))

    m = _REAL_RE.match(stripped)
    if m:
        return m.group(2), m.group(1)

    return None


def assign_delta_indices(
    raw_changes: list[tuple[int, str, str]],
) -> list[DeltaEvent]:
    """Group by simulation time; assign ``delta_idx`` 0,1,2... in file order."""
    if not raw_changes:
        return []

    events: list[DeltaEvent] = []
    current_time: int | None = None
    delta_idx = 0

    for time, signal, value in raw_changes:
        if current_time is None or time != current_time:
            current_time = time
            delta_idx = 0
        else:
            delta_idx += 1
        events.append(
            {
                "time": time,
                "delta_idx": delta_idx,
                "signal": signal,
                "value": value,
            }
        )

    return events


def _parse_vcd_text(text: str) -> list[DeltaEvent]:
    id_to_name: dict[str, str] = {}
    scope_stack: list[str] = []
    raw_changes: list[tuple[int, str, str]] = []
    current_time = 0
    in_definitions = True

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if in_definitions:
            if line.startswith("$enddefinitions"):
                in_definitions = False
                continue

            scope_m = _SCOPE_RE.match(line)
            if scope_m:
                scope_stack.append(scope_m.group(2).strip())
                continue
            if line == "$upscope":
                if scope_stack:
                    scope_stack.pop()
                continue

            var_parts = parse_var_line(line)
            if var_parts:
                var_id, ref_name, range_suffix, _size = var_parts
                id_to_name[var_id] = _hier_name(scope_stack, ref_name, range_suffix)
            continue

        time_m = _TIME_RE.match(line)
        if time_m:
            current_time = int(time_m.group(1))
            continue

        parsed = parse_value_line(line)
        if not parsed:
            continue
        var_id, value = parsed
        signal = id_to_name.get(var_id, f"<{var_id}>")
        raw_changes.append((current_time, signal, value))

    return assign_delta_indices(raw_changes)


def parse_vcd(path: str | Path) -> VcdParseResult:
    """Parse a VCD file into reconstructed delta events.

    Returns :class:`VcdParseResult` with ``events`` (list of
    ``{time, delta_idx, signal, value}``) and ``reason`` (non-empty when
    ``events`` is empty due to format deferral or read failure).

    For ``.fst`` inputs, returns empty events with
    ``reason="FST parse deferred; convert or use VCD for delta view"``.
    """
    p = Path(path)
    suffix = p.suffix.lower()

    if suffix == ".fst":
        return VcdParseResult(events=[], reason=_FST_DEFERRED)

    if suffix not in {".vcd", ""}:
        return VcdParseResult(
            events=[],
            reason=f"unsupported waveform suffix {suffix!r}; use .vcd",
        )

    if not p.is_file():
        return VcdParseResult(events=[], reason=f"file not found: {p}")

    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return VcdParseResult(events=[], reason=str(exc))

    return VcdParseResult(events=_parse_vcd_text(text))


def events_at_time(events: list[DeltaEvent], time: int) -> list[DeltaEvent]:
    """Return events at ``time`` sorted by ``delta_idx``."""
    return sorted(
        (e for e in events if e["time"] == time),
        key=lambda e: e["delta_idx"],
    )


def expand_timestep(events: list[DeltaEvent], time: int) -> list[dict[str, Any]]:
    """Return ordered delta steps at ``time`` for UI expansion.

    Each step is ``{"delta_idx": int, "changes": [{"signal", "value"}, ...]}``.
    """
    at_time = events_at_time(events, time)
    if not at_time:
        return []

    steps: list[dict[str, Any]] = []
    current_idx: int | None = None
    current_changes: list[dict[str, str]] = []

    for event in at_time:
        idx = event["delta_idx"]
        if current_idx is None:
            current_idx = idx
        if idx != current_idx:
            steps.append({"delta_idx": current_idx, "changes": current_changes})
            current_idx = idx
            current_changes = []
        current_changes.append(
            {"signal": event["signal"], "value": event["value"]}
        )

    if current_changes and current_idx is not None:
        steps.append({"delta_idx": current_idx, "changes": current_changes})

    return steps


def summary_at_time(events: list[DeltaEvent], time: int) -> dict[str, str]:
    """Return each signal's final value at the end of timestep ``time``.

    Carries forward the last known value from earlier timesteps, then applies
    all changes at ``time`` in ``delta_idx`` order (last write wins per signal).
    """
    state: dict[str, str] = {}

    for event in sorted(events, key=lambda e: (e["time"], e["delta_idx"])):
        if event["time"] > time:
            break
        state[event["signal"]] = event["value"]

    return dict(state)


def trace_to_json(events: list[DeltaEvent], limit: int = 500) -> dict[str, Any]:
    """Serialize events for the delta UI panel."""
    clipped = events[:limit]
    times = sorted({e["time"] for e in clipped})
    return {
        "kind": "reconstructed_delta",
        "disclaimer": (
            "Delta indices reconstructed from VCD file order, not VPI scheduler"
        ),
        "event_count": len(events),
        "returned_count": len(clipped),
        "truncated": len(events) > limit,
        "times": times,
        "events": clipped,
    }


def nearest_event_time(events: list[DeltaEvent], time: int) -> int | None:
    """Return closest simulation time that has at least one value change."""
    times = sorted({e["time"] for e in events})
    if not times:
        return None
    best = times[0]
    for t in times:
        if abs(t - time) < abs(best - time):
            best = t
    return best


def reconstruct(path: str | Path, time_ns: float) -> dict[str, Any]:
    """Build delta-panel rows for a waveform path at simulation time ``time_ns``.

    Used by the prototype UI (:func:`app.api_delta`). Returns
    ``{available, message, time_ns, rows, disclaimer?}`` where each row has
    ``signal``, ``prev``, ``value``, ``delta_idx``.
    """
    parsed = parse_vcd(path)
    time = int(time_ns)
    requested_time = time

    if not parsed.events:
        reason = parsed.reason or "no value-change events parsed"
        return {
            "available": False,
            "message": reason,
            "time_ns": time_ns,
            "rows": [],
            "disclaimer": "reconstructed from VCD file order (prototype)",
        }

    at_time = events_at_time(parsed.events, time)
    if not at_time:
        snapped = nearest_event_time(parsed.events, time)
        if snapped is not None and snapped != time:
            time = snapped
            at_time = events_at_time(parsed.events, time)
    if not at_time:
        return {
            "available": True,
            "message": f"no value changes at #{requested_time} (nearest: none)",
            "time_ns": requested_time,
            "snapped_time": None,
            "rows": [],
            "disclaimer": "reconstructed from VCD file order (prototype)",
        }

    prior = summary_at_time(parsed.events, time - 1) if time > 0 else {}
    rows: list[dict[str, Any]] = []
    for event in at_time:
        signal = event["signal"]
        rows.append(
            {
                "signal": signal,
                "prev": prior.get(signal, "—"),
                "value": event["value"],
                "delta_idx": event["delta_idx"],
            }
        )
        prior[signal] = event["value"]

    return {
        "available": True,
        "message": (
            f"{len(rows)} reconstructed delta step(s) at #{time}"
            + (f" (snapped from #{requested_time})" if time != requested_time else "")
            + " — VCD order, not VPI"
        ),
        "time_ns": requested_time,
        "snapped_time": time,
        "rows": rows,
        "disclaimer": "reconstructed from VCD file order (prototype)",
        "summary": summary_at_time(parsed.events, time),
        "steps": expand_timestep(parsed.events, time),
    }


def demo_vcd_text() -> str:
    """Minimal VCD for UI/delta testing when sim toolchain is unavailable."""
    return _self_test_sample_vcd()


def write_demo_vcd(path: str | Path) -> Path:
    """Write the demo VCD to *path* for delta/wave panel smoke tests."""
    target = Path(path)
    target.write_text(demo_vcd_text(), encoding="utf-8")
    return target


def _self_test_sample_vcd() -> str:
    return "\n".join(
        [
            "$date self-test $end",
            "$version VKing prototype delta $end",
            "$timescale 1ns $end",
            "$scope module tb $end",
            "$var wire 1 ! clk $end",
            "$var wire 1 \" rst_n $end",
            "$var wire 8 # data [7:0] $end",
            "$upscope $end",
            "$enddefinitions $end",
            "#0",
            "$dumpvars",
            "0!",
            "0\"",
            "b00000000 #",
            "$end",
            "#10",
            "1!",
            "1\"",
            "#10",
            "b00001111 #",
            "0!",
            "#20",
            "x!",
        ]
    )


def _run_self_test() -> None:
    result = _parse_vcd_text(_self_test_sample_vcd())
    assert len(result) == 8, f"expected 8 events, got {len(result)}"

    t10 = events_at_time(result, 10)
    assert len(t10) == 4, f"expected 4 events at #10, got {len(t10)}"
    assert t10[0]["delta_idx"] == 0 and t10[0]["signal"].endswith("clk")
    assert t10[1]["delta_idx"] == 1 and t10[1]["signal"].endswith("rst_n")
    assert t10[2]["delta_idx"] == 2 and "data" in t10[2]["signal"]
    assert t10[3]["delta_idx"] == 3 and t10[3]["value"] == "0"

    steps = expand_timestep(result, 10)
    assert len(steps) == 4
    assert steps[2]["changes"][0]["value"] == "00001111"

    summary = summary_at_time(result, 10)
    assert summary["tb.clk"] == "0"
    assert summary["tb.rst_n"] == "1"
    assert summary["tb.data[7:0]"] == "00001111"

    summary20 = summary_at_time(result, 20)
    assert summary20["tb.clk"] == "x"

    payload = trace_to_json(result, limit=3)
    assert payload["truncated"] is True
    assert payload["returned_count"] == 3
    assert payload["kind"] == "reconstructed_delta"

    fst = parse_vcd("waves.fst")
    assert not fst.events and _FST_DEFERRED in fst.reason

    print("delta.py self-test OK")
    print(json.dumps(trace_to_json(result, limit=5), indent=2))


if __name__ == "__main__":
    _run_self_test()
