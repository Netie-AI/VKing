#!/usr/bin/env python3
"""HTTP smoke test for all prototype API endpoints on port 9000."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:9000"
ROOT = Path(__file__).resolve().parent.parent


def _req(method: str, path: str, body: dict | None = None) -> tuple[int, dict | str]:
    url = BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw[:200]
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw[:200]


def main() -> int:
    failed = 0
    dut = (ROOT / "examples" / "counter.v").read_text(encoding="utf-8")

    checks: list[tuple[str, str, str | None, dict | None]] = [
        ("GET", "/api/doctor", None, None),
        ("GET", "/api/ai/status", None, None),
        ("GET", "/api/samples", None, None),
        ("GET", "/api/samples/counter", None, None),
        ("POST", "/api/parse", "/api/parse", {"source": dut}),
        ("POST", "/api/sync-tb", "/api/sync-tb", {"source": dut}),
    ]

    for method, label, path, body in checks:
        p = path or label
        code, data = _req(method, p, body)
        ok = 200 <= code < 300
        if label == "/api/doctor" and ok and isinstance(data, dict):
            ok = data.get("sim_ready") is True
            ver = (data.get("tools") or {}).get("verilator", {})
            print(f"  verilator: {ver.get('available')} ({ver.get('version_short') or 'missing'})")
        print(f"{'PASS' if ok else 'FAIL'} {method} {p} -> {code}")
        if not ok:
            failed += 1
            print(f"  {data}")

    code, sync = _req("POST", "/api/sync-tb", {"source": dut})
    tb = sync.get("tb") if isinstance(sync, dict) else None
    if not tb:
        print("FAIL no TB from sync-tb")
        return 1

    code, run = _req("POST", "/api/run", {"source": dut, "tb_source": tb})
    ok = 200 <= code < 300 and isinstance(run, dict)
    rid = run.get("manifest", {}).get("run_id") if ok else None
    g2 = run.get("manifest", {}).get("gate_results", {}).get("G2", {}) if ok else {}
    print(f"{'PASS' if ok and g2.get('status') == 'PASS' else 'FAIL'} POST /api/run -> {code} run_id={rid} G2={g2.get('status')}")
    if not ok or g2.get("status") != "PASS":
        failed += 1

    if rid:
        for path, body in (
            ("/api/waves", {"run_id": rid}),
            ("/api/delta", {"run_id": rid, "time_ns": 100000}),
            ("/api/netlist", {"source": dut}),
        ):
            code, data = _req("POST", path, body)
            ok = 200 <= code < 300
            extra = ""
            if path == "/api/waves" and isinstance(data, dict):
                extra = f" signals={len(data.get('signals', []))}"
            if path == "/api/delta" and isinstance(data, dict):
                extra = f" rows={len(data.get('rows', []))}"
            print(f"{'PASS' if ok else 'FAIL'} POST {path} -> {code}{extra}")
            if not ok:
                failed += 1

        code, _ = _req("POST", "/api/gtkwave", {"run_id": rid})
        print(f"{'PASS' if code == 200 else 'SKIP'} POST /api/gtkwave -> {code}")

    code, _ = _req("GET", "/")
    print(f"{'PASS' if code == 200 else 'FAIL'} GET / -> {code}")
    if code != 200:
        failed += 1

    return 1 if failed else 0


if __name__ == "__main__":
    print(f"API smoke against {BASE}\n")
    raise SystemExit(main())
