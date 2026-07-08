"""Toolchain detection for the prototype CLI (vking doctor)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

OSS_CAD_SUITE_URL = "https://github.com/YosysHQ/oss-cad-suite/releases"
OSS_CAD_SUITE_HINT = (
    f"Install YosysHQ oss-cad-suite (includes iverilog, vvp, verilator, gtkwave): "
    f"{OSS_CAD_SUITE_URL}"
)

_TOOLS = ("iverilog", "vvp", "verilator", "gtkwave")

_oss_bin_cached: Path | None | bool = False


def _oss_cad_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_root = os.environ.get("OSS_CAD_SUITE", "").strip()
    if env_root:
        candidates.append(Path(env_root) / "bin")
    candidates.append(Path(r"C:\oss-cad-suite\bin"))
    home = Path.home()
    candidates.append(home / "oss-cad-suite" / "bin")
    return candidates


def find_oss_cad_bin() -> Path | None:
    """Return the first existing oss-cad-suite ``bin`` directory."""
    global _oss_bin_cached
    if _oss_bin_cached is not False:
        return _oss_bin_cached  # type: ignore[return-value]
    found: Path | None = None
    for candidate in _oss_cad_candidates():
        if candidate.is_dir():
            found = candidate.resolve()
            break
    _oss_bin_cached = found
    return found


def tool_paths() -> dict[str, str | None]:
    """Return resolved executable paths for prototype toolchain tools."""
    ensure_path_env()
    paths: dict[str, str | None] = {}
    for tool in _TOOLS:
        resolved = shutil.which(tool)
        paths[tool] = str(Path(resolved).resolve()) if resolved else None
    oss_bin = find_oss_cad_bin()
    paths["oss_cad_suite_bin"] = str(oss_bin) if oss_bin else None
    return paths


def ensure_path_env() -> str | None:
    """Prepend discovered oss-cad-suite ``bin`` to ``PATH`` for subprocesses.

    Returns the prepended directory, or ``None`` if none was found.
    """
    oss_bin = find_oss_cad_bin()
    if not oss_bin:
        return None
    bin_str = str(oss_bin)
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    if parts and parts[0].lower() == bin_str.lower():
        return bin_str
    if any(p.lower() == bin_str.lower() for p in parts):
        return bin_str
    os.environ["PATH"] = bin_str + os.pathsep + current if current else bin_str
    return bin_str


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
    ensure_path_env()
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
    ensure_path_env()
    tools = check_toolchain()
    missing = [name for name, info in tools.items() if not info["available"]]
    sim_ready = tools["iverilog"]["available"] and tools["vvp"]["available"]
    oss_bin = find_oss_cad_bin()
    return {
        "tools": tools,
        "tool_paths": tool_paths(),
        "oss_cad_suite_bin": str(oss_bin) if oss_bin else None,
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
