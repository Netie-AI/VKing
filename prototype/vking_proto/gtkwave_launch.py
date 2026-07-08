"""GTKWave launcher with auto-loaded signal save file."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from .delta import parse_vcd
from .doctor import ensure_path_env, find_oss_cad_root, resolve_tool_exe


def _signal_priority(name: str) -> tuple[int, str]:
    lower = name.lower()
    if ".u_dut." in lower:
        leaf = lower.rsplit(".", 1)[-1]
        if leaf in ("q", "clk", "rst_n", "en", "valid", "ready"):
            return (0, name)
        return (1, name)
    if lower.endswith(".clk") or ".clk" in lower:
        return (2, name)
    if "rst" in lower or "reset" in lower:
        return (3, name)
    if lower.endswith(".q") or ".q" in lower.split(".")[-1]:
        return (4, name)
    return (9, name)


def list_vcd_signals(vcd_path: Path, *, limit: int = 24) -> list[str]:
    """Return hierarchical signal names from a VCD, DUT-first."""
    parsed = parse_vcd(vcd_path)
    names = sorted({e["signal"] for e in parsed.events}, key=_signal_priority)
    if not names:
        # Fall back to $var definitions via re-read if no events yet
        try:
            text = vcd_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return []
        import re

        scope: list[str] = []
        found: list[str] = []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("$scope"):
                parts = line.split()
                if len(parts) >= 3:
                    scope.append(parts[2])
            elif line == "$upscope":
                if scope:
                    scope.pop()
            elif line.startswith("$var"):
                m = re.match(r"^\$var\s+\S+\s+\d+\s+\S+\s+(.+?)\s+\$end", line)
                if m:
                    ref = m.group(1).strip()
                    hier = ".".join(scope + [ref.split()[0]])
                    found.append(hier)
        names = sorted(set(found), key=_signal_priority)
    return names[:limit]


def write_gtkw_save(vcd_path: Path, save_path: Path, signals: list[str] | None = None) -> Path:
    """Write a GTKWave save file that pre-selects key signals."""
    vcd_path = vcd_path.resolve()
    save_path = save_path.resolve()
    sigs = signals or list_vcd_signals(vcd_path)
    lines = [
        "[*][*]*",
        f"[dumpfile] {vcd_path.as_posix()}",
        f"[savefile] {save_path.as_posix()}",
        "[timestamp] 0",
        "[*][*]*",
    ]
    for sig in sigs:
        lines.append(f"[savename] {sig}")
    save_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return save_path


def launch_gtkwave(vcd_path: Path, *, save_path: Path | None = None) -> dict[str, Any]:
    """Launch GTKWave detached with VCD and optional save file."""
    ensure_path_env()
    root = find_oss_cad_root()
    if root:
        root_str = str(root)
        import os

        os.environ.setdefault("VERILATOR_ROOT", str(root / "share" / "verilator"))
        os.environ.setdefault("YOSYSHQ_ROOT", root_str + os.sep)
        os.environ.setdefault("GTK_EXE_PREFIX", root_str)
        os.environ.setdefault("GTK_DATA_PREFIX", root_str)

    gtkwave = resolve_tool_exe("gtkwave")
    if not gtkwave:
        raise RuntimeError("gtkwave not on PATH — install oss-cad-suite")

    vcd_path = vcd_path.resolve()
    if not vcd_path.is_file():
        raise FileNotFoundError(vcd_path)

    if save_path is None:
        save_path = vcd_path.with_suffix(".gtkw")
    write_gtkw_save(vcd_path, save_path)

    cmd = [gtkwave, str(vcd_path), str(save_path)]

    if sys.platform == "win32":
        subprocess.Popen(
            cmd,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
        )
    else:
        subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    return {
        "launched": True,
        "wave_path": str(vcd_path),
        "save_path": str(save_path),
        "signals": list_vcd_signals(vcd_path),
        "command": cmd,
    }
