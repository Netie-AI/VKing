"""Icarus simulation backend and gate runner (ISimBackend prototype)."""

from __future__ import annotations

import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .doctor import ensure_path_env, resolve_tool_exe
from .ingest import ModuleView, parse_tb_top_module, parse_verilog_source
from .manifest import ArtifactPaths, GateResult, GateStatus, RunManifest
from .tbgen import TbGenConfig, generate_clk_rst_smoke


_RUNS_ROOT = Path(__file__).resolve().parent.parent / "runs"
_RESULT_RE = re.compile(r"VKING_RESULT:\s*(PASS|FAIL|VACUOUS|TIMEOUT)", re.IGNORECASE)
_VACUITY_RE = re.compile(r"VKING_VACUITY:\s*(\S+)\s+(\d+)", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _tool_version(exe: str, flag: str = "-V") -> str | None:
    path = shutil.which(exe)
    if not path:
        return None
    try:
        proc = subprocess.run(
            [path, flag],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (proc.stdout or "") + (proc.stderr or "")
    first = out.strip().splitlines()[0] if out.strip() else exe
    return first.strip()


def _run_cmd(
    cmd: list[str],
    *,
    cwd: Path,
    log_path: Path | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if log_path is not None:
        log_path.write_text(
            "\n".join(
                [
                    "$ " + " ".join(cmd),
                    "--- stdout ---",
                    proc.stdout or "",
                    "--- stderr ---",
                    proc.stderr or "",
                    f"--- exit code: {proc.returncode} ---",
                ]
            ),
            encoding="utf-8",
        )
    return proc


def _parse_sim_log(log_text: str) -> tuple[str | None, list[dict[str, Any]]]:
    result: str | None = None
    vacuity: list[dict[str, Any]] = []
    for line in log_text.splitlines():
        m = _RESULT_RE.search(line)
        if m:
            result = m.group(1).upper()
        vm = _VACUITY_RE.search(line)
        if vm:
            vacuity.append({"check": vm.group(1), "count": int(vm.group(2))})
    return result, vacuity


def _gate_g0(dut_path: Path, run_dir: Path) -> GateResult:
    verilator = resolve_tool_exe("verilator")
    if not verilator:
        return GateResult(
            gate="G0",
            status=GateStatus.N_A,
            message="verilator not on PATH",
            backend="verilator",
        )
    log_path = run_dir / "g0_lint.log"
    proc = _run_cmd(
        [verilator, "--lint-only", "-Wall", dut_path.name],
        cwd=run_dir,
        log_path=log_path,
    )
    if proc.returncode == 0:
        return GateResult(
            gate="G0",
            status=GateStatus.PASS,
            message="lint clean",
            backend="verilator",
        )
    return GateResult(
        gate="G0",
        status=GateStatus.FAIL,
        message=f"verilator lint failed (exit {proc.returncode})",
        backend="verilator",
    )


def run_simulation(
    dut_path: str | Path,
    *,
    tb_source: str | None = None,
    view: ModuleView | None = None,
    tb_config: TbGenConfig | None = None,
    runs_root: str | Path | None = None,
    run_id: str | None = None,
) -> tuple[RunManifest, Path]:
    """
    Compile and simulate DUT + generated or supplied TB under prototype/runs/.

    Returns (RunManifest, run_directory).
    """
    dut_path = Path(dut_path).resolve()
    if not dut_path.is_file():
        raise FileNotFoundError(dut_path)

    dut_source = dut_path.read_text(encoding="utf-8")
    module_view = view or parse_verilog_source(dut_source)
    cfg = tb_config or TbGenConfig()
    tb_text = tb_source or generate_clk_rst_smoke(module_view, cfg)
    tb_top = parse_tb_top_module(tb_text) or cfg.tb_top

    ensure_path_env()
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        missing = [n for n, p in (("iverilog", iverilog), ("vvp", vvp)) if not p]
        raise RuntimeError(f"Missing toolchain on PATH: {', '.join(missing)}")

    root = Path(runs_root).resolve() if runs_root else _RUNS_ROOT
    root.mkdir(parents=True, exist_ok=True)
    rid = run_id or uuid.uuid4().hex[:12]
    run_dir = root / rid
    run_dir.mkdir(parents=True, exist_ok=True)

    dut_copy = run_dir / dut_path.name
    tb_path = run_dir / "tb.v"
    vvp_path = run_dir / "run.vvp"
    compile_log = run_dir / "compile.log"
    sim_log = run_dir / "run.log"
    wave_path = run_dir / cfg.wave_filename

    dut_copy.write_text(dut_source, encoding="utf-8")
    tb_path.write_text(tb_text, encoding="utf-8")

    flags = ["-g2012"]
    compile_cmd = [
        iverilog,
        *flags,
        "-o",
        vvp_path.name,
        "-s",
        tb_top,
        dut_copy.name,
        tb_path.name,
    ]

    manifest = RunManifest(
        run_id=rid,
        timestamp=_utc_now(),
        module=module_view.name,
        param_set={},
        dialect_profile="V2005-safe",
        backend="iverilog",
        backend_version=_tool_version("iverilog"),
        flags=flags,
        seed=None,
        timescale=module_view.timescale or cfg.timescale,
        artifact_paths=ArtifactPaths(
            dut=str(dut_copy),
            tb=str(tb_path),
            vvp=str(vvp_path),
            waves=str(wave_path),
            compile_log=str(compile_log),
            sim_log=str(sim_log),
        ),
    )

    manifest.gate_results["G0"] = _gate_g0(dut_copy, run_dir)

    comp = _run_cmd(compile_cmd, cwd=run_dir, log_path=compile_log)
    if comp.returncode != 0:
        manifest.gate_results["G1"] = GateResult(
            gate="G1",
            status=GateStatus.FAIL,
            message=f"iverilog compile failed (exit {comp.returncode})",
            backend="iverilog",
        )
        manifest.gate_results["G1.5"] = GateResult(
            gate="G1.5",
            status=GateStatus.FAIL,
            message="elaboration/bind failed during compile",
            backend="iverilog",
        )
        manifest.gate_results["G2"] = GateResult(
            gate="G2",
            status=GateStatus.SKIP,
            message="sim skipped due to compile failure",
            backend="iverilog",
        )
    else:
        manifest.gate_results["G1"] = GateResult(
            gate="G1",
            status=GateStatus.PASS,
            message="compile ok",
            backend="iverilog",
        )
        manifest.gate_results["G1.5"] = GateResult(
            gate="G1.5",
            status=GateStatus.PASS,
            message="elaboration/bind ok (via compile)",
            backend="iverilog",
        )

        sim_cmd = [vvp, "-n", "-l", sim_log.name, vvp_path.name]
        sim = _run_cmd(sim_cmd, cwd=run_dir, timeout=180)
        log_text = sim_log.read_text(encoding="utf-8") if sim_log.exists() else ""
        if not log_text:
            log_text = (sim.stdout or "") + (sim.stderr or "")

        sim_result, vacuity = _parse_sim_log(log_text)
        manifest.vacuity_report = vacuity

        if sim_result == "PASS":
            g2_status = GateStatus.PASS
            g2_msg = "reset/X sanity passed"
        elif sim_result == "VACUOUS":
            g2_status = GateStatus.VACUOUS
            g2_msg = "checks vacuous"
        elif sim_result == "TIMEOUT":
            g2_status = GateStatus.FAIL
            g2_msg = "watchdog timeout"
        elif sim_result == "FAIL":
            g2_status = GateStatus.FAIL
            g2_msg = "sim self-check failed"
        elif sim.returncode != 0:
            g2_status = GateStatus.FAIL
            g2_msg = f"vvp exited {sim.returncode}"
        else:
            g2_status = GateStatus.PASS
            g2_msg = "sim finished (custom TB — no VKING_RESULT marker)"

        manifest.gate_results["G2"] = GateResult(
            gate="G2",
            status=g2_status,
            message=g2_msg,
            backend="iverilog",
        )

    manifest_path = run_dir / "manifest.json"
    manifest.artifact_paths.manifest = str(manifest_path)
    manifest.write_json(manifest_path)
    return manifest, run_dir


def run(
    source: str,
    tb_source: str,
    makefile: str,
    filelist: str,
    module_name: str,
    runs_dir: Path,
    wave_filename: str = "waves.vcd",
    timescale: str = "1ns/1ps",
) -> dict[str, Any]:
    """FastAPI-compatible run entrypoint returning manifest dict + logs."""
    import uuid

    rid = uuid.uuid4().hex[:12]
    run_dir = Path(runs_dir) / rid
    run_dir.mkdir(parents=True, exist_ok=True)
    dut_path = run_dir / "dut.v"
    dut_path.write_text(source, encoding="utf-8")
    (run_dir / "Makefile").write_text(makefile, encoding="utf-8")
    (run_dir / "filelist.f").write_text(filelist, encoding="utf-8")

    view = parse_verilog_source(source)
    cfg = TbGenConfig(
        wave_filename=wave_filename,
        timescale=timescale or view.timescale or "1ns/1ps",
    )
    manifest, _ = run_simulation(
        dut_path,
        tb_source=tb_source,
        view=view,
        tb_config=cfg,
        runs_root=runs_dir,
        run_id=rid,
    )
    manifest.artifact_paths.filelist = str(run_dir / "filelist.f")
    sim_log_path = manifest.artifact_paths.sim_log
    sim_log = Path(sim_log_path).read_text(encoding="utf-8") if sim_log_path else ""
    return {
        "manifest": manifest.to_dict(),
        "log": sim_log,
        "artifact_paths": manifest.artifact_paths.model_dump(),
    }
