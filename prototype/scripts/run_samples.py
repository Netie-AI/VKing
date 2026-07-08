#!/usr/bin/env python3
"""Run all prototype/examples sample DUTs through sim + waves + delta checks."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vking_proto.delta import reconstruct  # noqa: E402
from vking_proto.doctor import doctor_report  # noqa: E402
from vking_proto.ingest import parse_verilog_source  # noqa: E402
from vking_proto.runner import run_simulation  # noqa: E402
from vking_proto.tbgen import generate_clk_rst_smoke  # noqa: E402
from vking_proto.waves import build_wave_traces  # noqa: E402

EXAMPLES = ROOT / "examples"
MANIFEST = EXAMPLES / "samples.json"


def main() -> int:
    health = doctor_report()
    if not health["sim_ready"]:
        print("FAIL: sim not ready — install oss-cad-suite at C:\\oss-cad-suite")
        return 1

    samples = json.loads(MANIFEST.read_text(encoding="utf-8"))
    failed = 0
    for item in samples:
        sid = item["id"]
        path = EXAMPLES / item["file"]
        source = path.read_text(encoding="utf-8")
        view = parse_verilog_source(source)
        tb = generate_clk_rst_smoke(view)
        run_id = f"sample_{sid}"
        runs = ROOT / "runs" / run_id
        if runs.exists():
            import shutil

            shutil.rmtree(runs)
        manifest, run_dir = run_simulation(
            path,
            tb_source=tb,
            view=view,
            runs_root=ROOT / "runs",
            run_id=run_id,
        )
        g2 = manifest.gate_results.get("G2")
        vcd = run_dir / "waves.vcd"
        ok_g2 = g2 and g2.status.value == "PASS"
        ok_vcd = vcd.is_file() and vcd.stat().st_size > 100
        w = build_wave_traces(vcd) if ok_vcd else {"signals": [], "t_max": 0}
        ok_waves = len(w.get("signals", [])) >= 2 and w.get("t_max", 0) > 0
        t_pick = max(1, w.get("t_max", 100) // 3)
        d = reconstruct(vcd, t_pick) if ok_vcd else {"rows": []}
        ok_delta = ok_vcd and d.get("available")
        status = "PASS" if ok_g2 and ok_vcd and ok_waves else "FAIL"
        print(
            f"{status} {sid}: G2={g2.status if g2 else '?'} "
            f"vcd={vcd.stat().st_size if ok_vcd else 0}B "
            f"signals={len(w.get('signals', []))} t_max={w.get('t_max')} "
            f"delta_rows={len(d.get('rows', []))}"
        )
        if status != "PASS":
            failed += 1
            if not ok_g2 and (run_dir / "compile.log").exists():
                print((run_dir / "compile.log").read_text(encoding="utf-8")[-500:])

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
