"""Regex-based generic view ingestion (IHdlFrontend prototype)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Port:
    name: str
    direction: str  # input | output | inout
    width_expr: str | None = None


@dataclass
class ModuleView:
    name: str
    ports: list[Port] = field(default_factory=list)
    timescale: str | None = None
    parameters: list[str] = field(default_factory=list)
    param_defaults: dict[str, str] = field(default_factory=dict)


_TIMESCALE_RE = re.compile(
    r"`timescale\s+(\S+)\s*/\s*(\S+)",
    re.IGNORECASE,
)

_MODULE_HEADER_RE = re.compile(
    r"\bmodule\s+(\w+)\s*"
    r"(?:#\s*\((?P<params>[^)]*)\))?\s*"
    r"(?:\(\s*(?P<ansi_ports>[^)]*)\)\s*)?",
    re.DOTALL,
)

_PORT_TOKEN_RE = re.compile(
    r"(?P<dir>input|output|inout)\s+"
    r"(?:(?:wire|reg|logic|signed|unsigned)\s+)*"
    r"(?:(?P<width>\[[^\]]+\])\s+)?"
    r"(?P<name>\w+)",
    re.IGNORECASE,
)

_NONANSI_PORT_RE = re.compile(
    r"^\s*(?P<dir>input|output|inout)\s+"
    r"(?:(?:wire|reg|logic|signed|unsigned)\s+)*"
    r"(?:(?P<width>\[[^\]]+\])\s+)?"
    r"(?P<name>\w+)\s*;",
    re.IGNORECASE | re.MULTILINE,
)

_PARAM_NAME_RE = re.compile(r"\bparameter\s+(?:\w+\s*=\s*)?(\w+)", re.IGNORECASE)
_PARAM_DEFAULT_RE = re.compile(
    r"parameter\s+(?:\w+\s+)?(\w+)\s*=\s*([^,;)]+)",
    re.IGNORECASE,
)

_MODULE_NAME_RE = re.compile(r"\bmodule\s+(\w+)\b", re.IGNORECASE)


def _strip_comments(source: str) -> str:
    result: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        if source.startswith("//", i):
            while i < n and source[i] != "\n":
                i += 1
            continue
        if source.startswith("/*", i):
            end = source.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        result.append(source[i])
        i += 1
    return "".join(result)


def _parse_parameters(param_blob: str | None) -> tuple[list[str], dict[str, str]]:
    if not param_blob or not param_blob.strip():
        return [], {}
    names: list[str] = []
    defaults: dict[str, str] = {}
    for m in _PARAM_DEFAULT_RE.finditer(param_blob):
        names.append(m.group(1))
        defaults[m.group(1)] = m.group(2).strip()
    if not names:
        names = [m.group(1) for m in _PARAM_NAME_RE.finditer(param_blob)]
    return names, defaults


def _parse_ansi_ports(port_blob: str) -> list[Port]:
    ports: list[Port] = []
    if not port_blob or not port_blob.strip():
        return ports
    for chunk in port_blob.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        match = _PORT_TOKEN_RE.search(chunk)
        if not match:
            continue
        ports.append(
            Port(
                name=match.group("name"),
                direction=match.group("dir").lower(),
                width_expr=match.group("width"),
            )
        )
    return ports


def _parse_nonansi_ports(source: str, header_names: list[str]) -> list[Port]:
    by_name: dict[str, Port] = {}
    for match in _NONANSI_PORT_RE.finditer(source):
        by_name[match.group("name")] = Port(
            name=match.group("name"),
            direction=match.group("dir").lower(),
            width_expr=match.group("width"),
        )
    if by_name:
        return list(by_name.values())
    return [Port(name=n, direction="inout") for n in header_names]


def parse_verilog_source(source: str) -> ModuleView:
    """Parse module name, ANSI/non-ANSI ports, and timescale from Verilog source."""
    cleaned = _strip_comments(source)
    ts_match = _TIMESCALE_RE.search(cleaned)
    timescale = None
    if ts_match:
        timescale = f"{ts_match.group(1)}/{ts_match.group(2)}"

    header = _MODULE_HEADER_RE.search(cleaned)
    if not header:
        raise ValueError("No module declaration found in Verilog source")

    name = header.group(1)
    parameters, param_defaults = _parse_parameters(header.group("params"))
    ansi_blob = header.group("ansi_ports")

    if ansi_blob and _PORT_TOKEN_RE.search(ansi_blob):
        ports = _parse_ansi_ports(ansi_blob)
    else:
        ordered: list[str] = []
        if ansi_blob:
            ordered = [p.strip() for p in ansi_blob.split(",") if p.strip()]
        ports = _parse_nonansi_ports(cleaned, ordered)

    return ModuleView(
        name=name,
        ports=ports,
        timescale=timescale,
        parameters=parameters,
        param_defaults=param_defaults,
    )


def list_module_names(source: str) -> list[str]:
    """Return module names in source order."""
    cleaned = _strip_comments(source)
    return _MODULE_NAME_RE.findall(cleaned)


def parse_tb_top_module(tb_source: str) -> str | None:
    """Guess testbench top module name from TB source."""
    names = list_module_names(tb_source)
    if not names:
        return None
    for name in reversed(names):
        lower = name.lower()
        if lower.endswith("_tb") or lower.endswith("_test") or lower.startswith("tb_"):
            return name
    return names[-1]


def analyze_tb_source(tb_source: str) -> dict[str, Any]:
    """Static checks on user/testbench Verilog before sim."""
    text = tb_source or ""
    top = parse_tb_top_module(text)
    has_dump = "$dumpfile" in text
    has_dumpvars = "$dumpvars" in text
    has_vking = "VKING_RESULT" in text
    warnings: list[str] = []
    if not has_dump or not has_dumpvars:
        warnings.append(
            "No $dumpfile/$dumpvars — Waves/Delta/GTKWave will be empty. "
            "Use “Insert wave dump” or add dumps targeting your TB module."
        )
    if not has_vking:
        warnings.append(
            "No VKING_RESULT marker — Summary “Result” stays blank; sim can still pass."
        )
    if top is None:
        warnings.append("Could not detect testbench module name — compile may fail.")
    return {
        "tb_top": top,
        "has_dumpfile": has_dump,
        "has_dumpvars": has_dumpvars,
        "has_vking_result": has_vking,
        "warnings": warnings,
    }


def wave_dump_snippet(tb_top: str, wave_file: str = "waves.vcd") -> str:
    """Minimal VCD dump block for a custom testbench."""
    return (
        "\n  initial begin\n"
        f'    $dumpfile("{wave_file}");\n'
        f"    $dumpvars(0, {tb_top});\n"
        "  end\n"
    )


def parse(source: str, top_module: str | None = None) -> dict[str, Any]:
    """Dict-shaped parse result for the FastAPI prototype UI."""
    errors: list[str] = []
    try:
        view = parse_verilog_source(source)
    except ValueError as exc:
        return {
            "module": top_module or "",
            "ports": [],
            "parameters": [],
            "errors": [str(exc)],
            "capability_matrix": {"iverilog": "unknown", "verilator": "unknown"},
        }

    if top_module and view.name != top_module:
        errors.append(f"module '{top_module}' not found; using '{view.name}'")

    ports: list[dict[str, str]] = []
    for port in view.ports:
        width = "0"
        if port.width_expr:
            m = re.match(r"\[([^\]]+)\]", port.width_expr)
            width = m.group(1).strip() if m else "0"
        ports.append(
            {"name": port.name, "direction": port.direction, "width": width}
        )

    parameters = [{"name": name, "default": "0"} for name in view.parameters]
    return {
        "module": view.name,
        "ports": ports,
        "parameters": parameters,
        "errors": errors,
        "capability_matrix": {"iverilog": "unknown", "verilator": "unknown"},
    }
