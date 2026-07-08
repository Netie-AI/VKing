"""Toolchain detection for the prototype CLI (vking doctor)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

OSS_CAD_SUITE_BUILD_URL = "https://github.com/YosysHQ/oss-cad-suite-build/releases/latest"
OSS_CAD_SUITE_HINT = (
    f"Install YosysHQ oss-cad-suite (iverilog, vvp, yosys, gtkwave): {OSS_CAD_SUITE_BUILD_URL}. "
    "Extract to C:\\oss-cad-suite (no spaces in path). See prototype/README.md."
)

_TOOLS = ("iverilog", "vvp", "verilator", "gtkwave", "yosys")

# oss-cad-suite on Windows ships Perl wrappers without .exe; real binaries use *_bin.exe.
_WINDOWS_ALIASES: dict[str, tuple[str, ...]] = {
    "verilator": ("verilator_bin.exe", "verilator.exe"),
    "verilator_coverage": ("verilator_coverage_bin.exe", "verilator_coverage.exe"),
}

_oss_bin_cached: Path | None | bool = False


def _oss_cad_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_root = os.environ.get("OSS_CAD_SUITE", "").strip()
    if env_root:
        candidates.append(Path(env_root) / "bin")
    candidates.append(Path(r"C:\oss-cad-suite\bin"))
    candidates.append(Path.home() / "oss-cad-suite" / "bin")
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


def find_oss_cad_root() -> Path | None:
    """Return oss-cad-suite root (contains bin/ and lib/)."""
    bin_dir = find_oss_cad_bin()
    if bin_dir is None:
        return None
    return bin_dir.parent


def ensure_path_env() -> str | None:
    """Prepend oss-cad-suite ``bin`` and ``lib`` to PATH (matches environment.bat)."""
    root = find_oss_cad_root()
    if not root:
        return None
    bin_str = str(root / "bin")
    lib_str = str(root / "lib")
    verilator_root = root / "share" / "verilator"
    if verilator_root.is_dir():
        os.environ["VERILATOR_ROOT"] = str(verilator_root)
    os.environ["YOSYSHQ_ROOT"] = str(root) + os.sep
    os.environ["GTK_EXE_PREFIX"] = str(root)
    os.environ["GTK_DATA_PREFIX"] = str(root)
    prepend = [bin_str, lib_str]
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    new_parts: list[str] = []
    for p in prepend:
        if not any(existing.lower() == p.lower() for existing in parts):
            new_parts.append(p)
    if new_parts:
        os.environ["PATH"] = os.pathsep.join(new_parts + parts)
    return bin_str


def resolve_tool_exe(name: str) -> str | None:
    """Resolve a toolchain executable, including Windows oss-cad aliases."""
    ensure_path_env()
    path = shutil.which(name)
    if path:
        return str(Path(path).resolve())

    candidates: list[str] = [f"{name}.exe"]
    if os.name == "nt":
        candidates = list(_WINDOWS_ALIASES.get(name, ())) + candidates

    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return str(Path(path).resolve())

    oss_bin = find_oss_cad_bin()
    if oss_bin:
        for candidate in candidates:
            direct = oss_bin / candidate
            if direct.is_file():
                return str(direct.resolve())
    return None


def short_version(full: str | None) -> str | None:
    """Compact version label for UI (hide long build strings)."""
    if not full:
        return None
    m = re.search(r"version\s+([\d.]+(?:[+][\d\w-]+)?)", full, re.I)
    if m:
        return m.group(1)
    m = re.search(r"\bv([\d.]+)", full)
    if m:
        return m.group(1)
    m = re.match(r"^(\S+)\s+([\d.+]+)", full)
    if m:
        return m.group(2).split()[0]
    return full[:16]


def tool_paths() -> dict[str, str | None]:
    """Return resolved executable paths for prototype toolchain tools."""
    ensure_path_env()
    paths: dict[str, str | None] = {}
    for tool in _TOOLS:
        resolved = resolve_tool_exe(tool)
        paths[tool] = resolved
    oss_bin = find_oss_cad_bin()
    paths["oss_cad_suite_bin"] = str(oss_bin) if oss_bin else None
    return paths


def _probe_version(exe: str) -> str | None:
    for flag in ("-V", "--version", "-version"):
        try:
            proc = subprocess.run(
                [exe, flag],
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
    return exe


def check_toolchain() -> dict[str, dict[str, Any]]:
    """Return per-tool availability and version strings."""
    ensure_path_env()
    report: dict[str, dict[str, Any]] = {}
    for tool in _TOOLS:
        path = resolve_tool_exe(tool)
        version = _probe_version(path) if path else None
        report[tool] = {
            "available": path is not None,
            "path": path,
            "version": version,
            "version_short": short_version(version),
        }
    return report


def doctor_report() -> dict[str, Any]:
    """Full doctor status dict with install guidance."""
    ensure_path_env()
    tools = check_toolchain()
    missing = [name for name, info in tools.items() if not info["available"]]
    sim_ready = tools["iverilog"]["available"] and tools["vvp"]["available"]
    oss_bin = find_oss_cad_bin()
    oss_root = find_oss_cad_root()
    return {
        "tools": tools,
        "tool_paths": tool_paths(),
        "oss_cad_suite_bin": str(oss_bin) if oss_bin else None,
        "oss_cad_suite_root": str(oss_root) if oss_root else None,
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
