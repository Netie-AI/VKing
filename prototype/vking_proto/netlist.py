"""Yosys netlist JSON for schematic view (netlistsvg)."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .doctor import ensure_path_env
from .ingest import parse_verilog_source


def _run_yosys_json(dut_path: Path, top: str) -> tuple[dict[str, Any] | None, str]:
    ensure_path_env()
    yosys = shutil.which("yosys")
    if not yosys:
        return None, "yosys not on PATH — install oss-cad-suite"

    out_json = dut_path.parent / "netlist.json"
    script = f"read_verilog {dut_path.name}; hierarchy -top {top}; proc; opt; write_json {out_json.name}"
    proc = subprocess.run(
        [yosys, "-q", "-p", script],
        cwd=dut_path.parent,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    log = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0 or not out_json.is_file():
        return None, f"yosys failed (exit {proc.returncode}): {log[-2000:]}"
    try:
        data = json.loads(out_json.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid netlist JSON: {exc}"
    return data, log


def build_netlist(source: str, top_module: str | None = None) -> dict[str, Any]:
    """Elaborate Verilog to Yosys JSON for netlistsvg schematic rendering."""
    view = parse_verilog_source(source)
    top = top_module or view.name

    with tempfile.TemporaryDirectory(prefix="vking_nl_") as tmp:
        dut_path = Path(tmp) / "dut.v"
        dut_path.write_text(source, encoding="utf-8")
        data, log = _run_yosys_json(dut_path, top)
        if data is None:
            return {
                "ok": False,
                "message": log,
                "top": top,
                "netlist": None,
                "netlistsvg_url": "https://netlistsvg.com/app",
            }
        return {
            "ok": True,
            "message": f"netlist for top '{top}'",
            "top": top,
            "netlist": data,
            "module_count": len(data.get("modules", {})),
            "netlistsvg_url": "https://netlistsvg.com/app",
            "hint": (
                "Paste the netlist JSON into netlistsvg (link above) or use the in-app schematic panel."
            ),
        }
