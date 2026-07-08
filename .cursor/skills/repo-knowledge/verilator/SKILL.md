---
name: verilator-repo-knowledge
description: Load-bearing capability card for verilator — populated by repo-surveyor subagent. What Vking's frozen interfaces (§4.4) need from Verilator.
---

# verilator — capability card

**Status:** Surveyed 2026-07-08 · **Provenance:** L2_sim_active (repo read + commit pinned)

## Identity

| Field | Value |
|---|---|
| **What** | Fast **Verilog/SystemVerilog compiler-simulator**. Verilates RTL to optimized C++ (or SystemC), optionally builds an executable, runs assertions/coverage, emits FST/VCD traces. Also usable as a standalone linter. |
| **Upstream** | https://github.com/verilator/verilator |
| **Pinned commit** | `6c20fdb7bd94db311f3055583c7bb7c74d287ba3` (`v5.050-40-g6c20fdb7b`, "Optimize assertion NFAs using bit-vector ring buffers (#7885)", 2026-07-07) |
| **License** | **LGPL-3.0-only OR Artistic-2.0** (dual-licensed; `README.rst` SPDX). Vking invokes `verilator` / `verilator_coverage` as **GPL-adjacent subprocesses only** — never link `libverilated.a` into Vking (same rule as Icarus/GTKWave, master plan §10). |
| **Binaries** | `verilator` (compile/lint driver), `verilator_coverage` (post-run coverage merge/report), plus runtime helpers (`verilator_gantt`, `verilator_profcfunc`, …) — only the first two are load-bearing for v0.x. |

Vking does **not** bundle Verilator. `vking doctor` probes PATH (oss-cad-suite ships it per master plan §10).

## Vking interface mapping

| §4.4 interface | Role | Gates / stage |
|---|---|---|
| **`IGateRunner`** | **Primary.** G0 lint (`--lint-only -Wall`); DUT capability-matrix probe (same command); G3 coverage grading via `verilator_coverage` after sim. | G0, G3 (v0.2+); G2 **never** on Verilator |
| **`ISimBackend`** | **Primary (v0.2+).** Verilate + build + run TB+DUT for Profile B ("SV-TB") and fast regress/coverage lane. | G1 compile, G3 sim+assertions+coverage; stubbed v0.1 |
| **`ITBGenerator`** | Indirect. Profile B templates may emit SVA/`cover property`; Verilator is the only OSS backend that runs them. Generated timescale + negedge-drive style law must match compile flags. | Profile B only |
| **`IUIRenderer`** | Indirect. Verilator lane emits FST via `--trace-fst`; GTKWave opens the artifact — not Verilator's job in v0.x. | Wave path via manifest |
| **Others** | No load-bearing coupling. cocotb/VPI (`--vpi`) is Profile C / v0.5+. |

Backend policy matrix (§4.3): lint + coverage + SVA → Verilator; X/reset sanity (G2) → **Icarus only** (Verilator's 2-state model makes G2 near-vacuous).

## Load-bearing entry points (5)

### 1. G0 lint + DUT capability probe — `verilator --lint-only -Wall`

Master plan G0 contract. Lint only; no C++ emission (`--build` / `--binary` incompatible).

```text
verilator --lint-only -Wall -Mdir <obj_dir> [--top-module <top>] [--timescale-override <tu>/<tp>] <sources...>
```

- **Warnings are errors by default** (fail-closed for generated artifacts). Use `-Wno-fatal` only for exploratory DUT advisory runs, not generated TB/catalog RTL.
- Implies `--timing` unless `--no-timing` is passed — for lint-only DUT probes on delay-free RTL, `--no-timing` avoids coroutine requirements.
- For incomplete/black-box DUT lint: `--bbox-sys` (PLI `$` calls) / `--bbox-unsup` (UDP, tran, …) — use sparingly; black-boxed code simulates incorrectly.
- Waiver files (`.vlt`) must appear **before** the sources they waive on the command line.
- Record `verilator --version` output in run manifest `backend_version`.

Reference harness: `test_regress/driver.py` `lint()` → `--lint-only`.

### 2. ISimBackend compile+run — `verilator --cc --exe --build --timing` (or `--binary`)

Fast sim lane for Profile B and `vking regress --profile fast`. Two-phase: Verilate (Perl driver) → GNU Make build → run executable.

Minimal pattern (Vking-generated C++ `sim_main.cpp` + file list):

```text
verilator --cc --exe --build --timing \
  -Mdir <obj_dir> --prefix V<top> --top-module <top> \
  [--trace-fst] [--coverage] \
  -CFLAGS "-std=c++17" \
  <sources...> <sim_main.cpp>
```

`--binary` is an alias for `--main --exe --build --timing` (single-shot sim binary).

- **`--build` requires GNU Make** on PATH; Verilator owns the build when `--build` is set.
- Assertions enabled **by default since 5.038** — do **not** pass `--no-assert` for G3.
- Profile A (V2005-safe) TBs also compile here, but G2 X-checks still run on Icarus.
- Runtime: `./obj_dir/V<top> +verilator+seed+<n> [+verilator+quiet]`; seed reproducibility via `+verilator+seed+` (0 → auto-seed, exposed via `$get_initial_random_seed`).
- Exit non-zero on assertion failure (unless `--no-stop-on-assert-failure` at compile time — never use for gates).

Reference harness: `test_regress/driver.py` default `-cc` flow; `--binary` tests under `test_regress/t/`.

### 3. Wave artifact — `--trace-fst`

Verilator lane wave dumps for manifest → GTKWave (not `$dumpfile`/`$dumpvars` — those are Icarus style law).

```text
verilator ... --trace-fst [--trace-max-width <w>] ...
# C++ wrapper must call trace dump APIs or use --main/--binary auto wrapper
```

- Prefer `--trace-fst` over deprecated `--trace` (VCD default).
- FST tracing has width/thread limits documented in `exe_verilator.rst`; wide buses may need `--trace-max-width`.
- Generated-TB style law still applies to *Icarus* `$dumpfile`; Verilator lane uses C++ trace API / `--trace-fst` path separately — manifest must record which backend produced which wave file.

### 4. G3 coverage — compile with `--coverage`, run with `+verilator+coverage+file+`, grade with `verilator_coverage`

Coverage instrumentation at Verilate time; collection at sim end.

**Compile:**

```text
verilator ... --coverage [--coverage-user] [--coverage-per-instance] ...
```

`--coverage` enables line/toggle/expr/fsm/user/property buckets. For template `cover property` / covergroups, `--coverage-user` (included in `--coverage` alias) is required.

**Run:**

```text
./V<top> +verilator+coverage+file+<obj_dir>/coverage.dat
```

Or call `Verilated::threadContextp()->coveragep()->write("coverage.dat")` from C++ `sim_main` at `$finish`.

**Grade (IGateRunner G3 floor):**

```text
verilator_coverage --report summary <obj_dir>/coverage.dat
verilator_coverage --annotate-min <N> --annotate <out_dir> <coverage.dat>   # points below N marked "%"
```

- `verilator_coverage --annotate-min` defaults to **10 hits** — natural hook for Vking's configurable coverage floor (distinct from vacuity counters, which are TB-side).
- Merge multi-run: `verilator_coverage --write merged.dat run1.dat run2.dat ...`
- lcov export: `--write-info` for external HTML/codecov (optional; not required v0.x).

Reference: `test_regress/t/t_vlcov_hier_report_runtime.py`.

### 5. Toolchain probe — `verilator --version` / `verilator_coverage --version`

For `vking doctor` and run manifest `{backend, backend_version, flags}`. Verilated sim executables also accept `+verilator+version` at runtime.

## Quirks / gotchas

1. **Not a 4-state simulator.** Tristate `z` and unknown `x` are handled in limited contexts for speed. **Never run G2 (X/reset sanity) on Verilator** — master plan hard rule; report `N/A (backend unsupported)` in capability matrix, not PASS.

2. **Lint vs sim timing mode.** `--lint-only` implies `--timing` unless `--no-timing`. Sim builds for generated TBs need `--timing` (or `--binary`) for delays/events; coroutines require GCC ≥10 / Clang ≥5.

3. **Warnings fail the gate.** Default lint exits non-zero on warnings. G0 fail-closed for generated code matches this. DUT advisory lane may map `vking-waivers.toml` → `.vlt` waiver files (listed before sources) or `-Wno-<code>` — never for catalog/generated RTL.

4. **Timescale discipline.** Verilator default when `` `timescale`` missing: `1ps/1ps`. Vking style law requires explicit `` `timescale`` in every generated file; runner should pass matching `--timescale-override` to both backends to avoid TIMESCALEMOD divergence warnings and sim-time skew.

5. **Two-step workflow.** Unlike `iverilog`+`vvp`, Verilator is compile-to-C++ then execute. `ISimBackend` must manage `obj_dir`, rebuild invalidation, and surface **compile** vs **run** failures separately (G1 vs G3).

6. **Make is mandatory for `--build`.** Windows CI must have Make (oss-cad-suite / MSYS). `--make json` exists for alternate build systems; v0.x should stick to `--build` + gmake for simplicity.

7. **Assertion / vacuity split.** SVA failures stop sim (G3 assert pass). **Vacuity** (antecedent counters ≥ N) is Vking TB-side per style law §6.1 — Verilator does not compute Vking vacuity reports; do not conflate with `verilator_coverage` thresholds.

8. **Coverage ≠ functional proof.** `--annotate-min` / `--report summary` measure bucket hits, not intent. Master plan honesty banner applies; G3 green ≠ "verified correct."

9. **Profile split.** Profile A runs both backends; Profile B (SVA, concurrent assertions, rich SV) is **Verilator-only** — Icarus gets `N/A`, not skip. Immediate assertions in V2005 TBs work on both.

10. **VPI / cocotb deferred.** `--vpi` enables limited IEEE VPI; runtime `+verilator+vpi+<lib>` is **POSIX-only** (Windows must statically link). Profile C target — not v0.x `ISimBackend` default.

11. **SDF / analog unsupported.** No gate-level SDF annotation path here; timing lane is OpenSTA→SDF→Icarus (S4), not Verilator.

12. **FSM coverage experimental.** `--coverage-fsm` heuristics and metacomments may change; treat FSM bins as best-effort until pinned behavior is regression-locked in Vking CI.

## Minimal Vking contracts

**G0 (IGateRunner):**

```text
verilator --lint-only -Wall -Mdir <obj> --top-module <top> --timescale-override 1ns/1ns @<filelist>
# exit 0 required for generated artifacts
```

**Fast regress sim (ISimBackend, Profile B):**

```text
verilator --cc --exe --build --timing -Mdir <obj> --top-module <top> \
  --trace-fst --coverage --timescale-override 1ns/1ns @<filelist> <sim_main.cpp>
./<obj>/V<top> +verilator+seed+<seed> +verilator+coverage+file+<obj>/coverage.dat
verilator_coverage --report summary <obj>/coverage.dat
```

**Doctor:**

```text
verilator --version
verilator_coverage --version
```

## Key source anchors

| Path | Why |
|---|---|
| `docs/guide/exe_verilator.rst` | All compile flags: `--lint-only`, `-Wall`, `--binary`, `--coverage`, `--trace-fst`, `--timescale-override` |
| `docs/guide/simulating.rst` | Runtime behavior, coverage dump, sim summary report |
| `docs/guide/exe_verilator_coverage.rst` | G3 floor hooks: `--report`, `--annotate-min` (default 10) |
| `docs/guide/verilating.rst` | Verilate workflow, module binding, `--top-module` |
| `test_regress/driver.py` | Upstream canonical lint/compile/run flag patterns |
| `test_regress/t/t_vlcov_hier_report_runtime.py` | End-to-end coverage + `verilator_coverage --report` reference |
