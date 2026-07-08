"""Verilog dump helpers for dual FST + VCD artifact emission (prototype).

GTKWave reads ``.fst`` (Icarus: ``vvp -fst sim.vvp``). The delta reconstruction
panel reads ``.vcd`` via :mod:`vking_proto.delta`.

**Icarus caveat:** ``vvp -fst`` routes the dumper to FST. For a single sim run
to produce both formats you typically need either:
- two dump initial blocks (same hierarchy, different ``$dumpfile`` targets) with
  the understanding that the active dumper follows the last ``$dumpfile``, or
- a dedicated VCD run without ``-fst`` for the delta panel.

Until ``tbgen`` emits dual dumps by default, paste
:func:`verilog_dual_dump_blocks` into generated TBs or document the VCD path in
the run manifest ``artifact_paths``.
"""

from __future__ import annotations


def verilog_dual_dump_blocks(
    fst_path: str = "waves.fst",
    vcd_path: str = "waves.vcd",
    dumpvars_depth: int = 0,
    hierarchy: str = "tb.dut",
) -> str:
    """Return Verilog ``initial`` blocks for FST (GTKWave) and VCD (delta panel).

    Parameters
    ----------
    fst_path:
        Target path when sim is run with ``vvp -fst``.
    vcd_path:
        Target path for reconstructed delta view (``vvp`` without ``-fst``, or
        a second dump pass).
    dumpvars_depth:
        First argument to ``$dumpvars`` (0 = all hierarchy under node).
    hierarchy:
        Root hierarchy path passed to ``$dumpvars``.
    """
    return "\n".join(
        [
            "// --- VKing prototype: dual waveform dumps ---",
            "// FST -> GTKWave (run: vvp -fst sim.vvp)",
            "initial begin",
            f'  $dumpfile("{fst_path}");',
            f"  $dumpvars({dumpvars_depth}, {hierarchy});",
            "end",
            "",
            "// VCD -> delta reconstruction panel (see vking_proto.delta)",
            "// Prefer a VCD-only vvp pass if -fst prevents .vcd emission.",
            "initial begin",
            f'  $dumpfile("{vcd_path}");',
            f"  $dumpvars({dumpvars_depth}, {hierarchy});",
            "end",
            "// --- end dual dump blocks ---",
        ]
    )


def manifest_wave_paths(
    run_id: str,
    fst_name: str = "waves.fst",
    vcd_name: str = "waves.vcd",
) -> dict[str, str]:
    """Suggested ``artifact_paths`` entries for a run manifest."""
    return {
        "waves": f"runs/{run_id}/{fst_name}",
        "waves_vcd": f"runs/{run_id}/{vcd_name}",
    }


def tbgen_recommendation_note() -> str:
    """One-line note for tbgen / codegen docs until dual dump is default."""
    return (
        "Emit $dumpfile for both .fst (vvp -fst, GTKWave) and .vcd "
        "(delta reconstruction); record both paths in run manifest."
    )
