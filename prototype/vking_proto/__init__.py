"""Vking prototype core — vertical slice backend (v0.1)."""

__version__ = "0.1.0-prototype"

from .manifest import ArtifactPaths, GateResult, GateStatus, RunManifest
from .ingest import ModuleView, Port, parse_verilog_source
from .tbgen import TbGenConfig, generate_clk_rst_smoke
from .runner import run_simulation
from .doctor import check_toolchain, doctor_report

__all__ = [
    "__version__",
    "ArtifactPaths",
    "GateResult",
    "GateStatus",
    "RunManifest",
    "ModuleView",
    "Port",
    "parse_verilog_source",
    "TbGenConfig",
    "generate_clk_rst_smoke",
    "run_simulation",
    "check_toolchain",
    "doctor_report",
]
