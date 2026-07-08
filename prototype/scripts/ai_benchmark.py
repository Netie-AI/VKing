#!/usr/bin/env python3
"""Benchmark AI-generated testbenches: compile + sim across configured models."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vking_proto.ai_generate import generate_verilog, verify_verilog  # noqa: E402
from vking_proto.config import benchmark_models, get_ai_config  # noqa: E402
from vking_proto.delta import reconstruct  # noqa: E402
from vking_proto.doctor import doctor_report  # noqa: E402
from vking_proto.ingest import parse_verilog_source  # noqa: E402
from vking_proto.runner import run_simulation  # noqa: E402
from vking_proto.waves import build_wave_traces  # noqa: E402

EXAMPLES = ROOT / "examples"
MANIFEST = EXAMPLES / "samples.json"
OUT_DIR = ROOT / "runs" / "ai_benchmark"


def _score(row: dict) -> str:
    if not row.get("ai_ok"):
        return "AI_FAIL"
    if not row.get("verify_ok"):
        return "VERIFY_FAIL"
    g1 = row.get("g1")
    g2 = row.get("g2")
    if g1 != "PASS":
        return "COMPILE_FAIL"
    if g2 != "PASS":
        return "SIM_FAIL"
    if not row.get("waves_ok"):
        return "WAVES_FAIL"
    return "PASS"


def main() -> int:
    health = doctor_report()
    if not health["sim_ready"]:
        print("FAIL: sim not ready")
        return 1

    models = benchmark_models()
    if not models:
        print("FAIL: no AI keys — set GROQ_API_KEY or OPENROUTER_API_KEY")
        return 1

    samples = json.loads(MANIFEST.read_text(encoding="utf-8"))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    for model_cfg in models:
        provider = model_cfg["provider"]
        model = model_cfg["model"]
        if not get_ai_config(provider=provider, model=model):
            print(f"SKIP {provider}/{model} — no API key")
            continue

        for item in samples:
            sid = item["id"]
            path = EXAMPLES / item["file"]
            source = path.read_text(encoding="utf-8")
            view = parse_verilog_source(source)
            tag = f"{provider}_{model.replace('/', '_')}_{sid}"
            print(f"--- {tag} ---")

            t0 = time.perf_counter()
            ai = generate_verilog(source, mode="tb", provider=provider, model=model)
            ai_ms = ai.get("latency_ms", 0)

            row: dict = {
                "sample": sid,
                "provider": provider,
                "model": model,
                "ai_ok": ai.get("ok"),
                "ai_error": ai.get("error"),
                "ai_latency_ms": ai_ms,
                "verify_ok": False,
                "verify_errors": [],
                "g1": None,
                "g2": None,
                "g0": None,
                "vking_result": None,
                "waves_ok": False,
                "delta_ok": False,
                "score": "AI_FAIL",
            }

            if not ai.get("ok") or not ai.get("verilog"):
                row["score"] = _score(row)
                results.append(row)
                print(f"  AI FAIL: {ai.get('error')}")
                continue

            verify = ai.get("verify") or verify_verilog(ai["verilog"], mode="tb")
            row["verify_ok"] = verify.get("ok", False)
            row["verify_errors"] = verify.get("errors", [])

            run_dir = OUT_DIR / tag
            if run_dir.exists():
                import shutil

                shutil.rmtree(run_dir)

            try:
                manifest, run_path = run_simulation(
                    path,
                    tb_source=ai["verilog"],
                    view=view,
                    runs_root=OUT_DIR,
                    run_id=tag,
                )
            except Exception as exc:  # noqa: BLE001
                row["score"] = "COMPILE_FAIL"
                row["ai_error"] = str(exc)
                results.append(row)
                print(f"  RUN FAIL: {exc}")
                continue

            (run_path / "ai_tb.v").write_text(ai["verilog"], encoding="utf-8")
            g = manifest.gate_results
            row["g0"] = g.get("G0").status.value if g.get("G0") else None
            row["g1"] = g.get("G1").status.value if g.get("G1") else None
            row["g2"] = g.get("G2").status.value if g.get("G2") else None

            log_path = manifest.artifact_paths.sim_log
            if log_path and Path(log_path).exists():
                log = Path(log_path).read_text(encoding="utf-8")
                import re

                m = re.search(r"VKING_RESULT:\s*(\w+)", log, re.I)
                if m:
                    row["vking_result"] = m.group(1).upper()

            vcd = run_path / "waves.vcd"
            if vcd.is_file() and vcd.stat().st_size > 100:
                w = build_wave_traces(vcd)
                row["waves_ok"] = len(w.get("signals", [])) >= 2
                d = reconstruct(vcd, max(1, w.get("t_max", 100) // 3))
                row["delta_ok"] = bool(d.get("available"))

            row["score"] = _score(row)
            row["total_ms"] = int((time.perf_counter() - t0) * 1000)
            results.append(row)
            print(
                f"  {row['score']} verify={row['verify_ok']} "
                f"G1={row['g1']} G2={row['g2']} result={row['vking_result']} "
                f"ai={ai_ms}ms total={row['total_ms']}ms"
            )

    report_path = OUT_DIR / "report.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print("\n=== Summary ===")
    by_model: dict[str, list[str]] = {}
    for r in results:
        key = f"{r['provider']}/{r['model']}"
        by_model.setdefault(key, []).append(r["score"])
    for key, scores in by_model.items():
        passed = sum(1 for s in scores if s == "PASS")
        print(f"{key}: {passed}/{len(scores)} PASS  scores={scores}")

    print(f"\nReport: {report_path}")
    failed = any(r["score"] != "PASS" for r in results)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
