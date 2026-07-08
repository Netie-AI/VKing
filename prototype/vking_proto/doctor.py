"""Toolchain detection for the prototype CLI (vking doctor)."""

from __future__ import annotations

import shutil
import subprocess
from typing import Any


OSS_CAD_SUITE_URL = "https://github.com/YosysHQ/oss-cad-suite/releases"
OSS_CAD_SUITE_HINT = (
    f"Install YosysHQ oss-cad-suite (includes iverilog, vvp, verilator, gtkwave): "
    f"{OSS_CAD_SUITE_URL}"
)

_TOOLS = ("iverilog", "vvp", "verilator", "gtkwave")


def _probe_version(exe: str) -> str | None:
    path = shutil.which(exe)
    if not path:
        return None
    for flag in ("-V", "--version", "-version"):
        try:
            proc = subprocess.run(
                [path, flag],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        out = ((proc.stdout or "") + (proc.stderr or "")).strip()
        if out:
            return out.splitlines()[0].strip()
    return path


def check_toolchain() -> dict[str, dict[str, Any]]:
    """Return per-tool availability and version strings."""
    report: dict[str, dict[str, Any]] = {}
    for tool in _TOOLS:
        path = shutil.which(tool)
        report[tool] = {
            "available": path is not None,
            "path": path,
            "version": _probe_version(tool) if path else None,
        }
    return report


def doctor_report() -> dict[str, Any]:
    """Full doctor status dict with install guidance."""
    tools = check_toolchain()
    missing = [name for name, info in tools.items() if not info["available"]]
    sim_ready = tools["iverilog"]["available"] and tools["vvp"]["available"]
    return {
        "tools": tools,
        "sim_ready": sim_ready,
        "lint_ready": tools["verilator"]["available"],
        "waves_ready": tools["gtkwave"]["available"],
        "missing": missing,
        "install_hint": OSS_CAD_SUITE_HINT if missing else None,
        "ok": sim_ready,
    }


def check() -> dict[str, Any]:
    """Alias for FastAPI prototype UI."""
    return doctor_report()
