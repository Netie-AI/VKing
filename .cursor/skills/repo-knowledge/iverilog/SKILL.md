---
name: iverilog-repo-knowledge
description: Load-bearing capability card for iverilog — populated by repo-surveyor subagent. What Vking's frozen interfaces (§4.4) need from Icarus Verilog.
---

# iverilog — capability card

## Identity

| Field | Value |
|-------|-------|
| **What** | Icarus Verilog — GPL Verilog/SystemVerilog compiler + VVP 4-state event simulator. `iverilog` compiles HDL to a VVP bytecode file; `vvp` executes it. Not a monolithic simulator — a compiler toolchain with a pluggable code-generator back end (default target `vvp`). |
| **Upstream** | https://github.com/steveicarus/iverilog |
| **Pinned commit** | `e02a0bc2ec21ace2a65a88288f0d4dcab56bb901` (2026-07-06; describe: `s20260301-263-ge02a0bc2e`) |
| **Package version** | 14.0 (devel) per `configure.ac` — use `iverilog -V` / `vvp -V` at runtime for manifest `backend_version`. |
| **License** | **GPL-2.0** (`COPYING`). Vking invokes `iverilog`/`vvp` as **subprocesses on PATH**; do not vendor or redistribute GPL binaries (§9 toolchain policy). |

## Vking interface mapping (§4.4 / §7)

| Vking interface | Gate / role | How iverilog serves it |
|-----------------|-------------|------------------------|
| **ISimBackend** | G1 compile, sim run | Two-step: `iverilog` → `.vvp`, then `vvp` on that file. 4-state, event/delta-accurate reference lane (§4.3). |
| **IGateRunner** | G1 | `iverilog` compile; non-zero exit = fail-closed. |
| **IGateRunner** | G1.5 elaboration/bind | Elaboration is **inside** the `iverilog` compile pipeline (`ivl`); no separate elab binary. Width/bind/top errors surface as compile failures on the same command. |
| **IGateRunner** | G2 reset/X sanity | **Always Icarus, 4-state** (§7). Run compiled design with `vvp`; X propagation is real (contrast Verilator 2-state). |

## Entry points (load-bearing only)

### 1. `iverilog` — compile driver (`driver/main.c`)

Primary subprocess for **G1** and **G1.5**. Orchestrates `ivlpp` (preprocess) → `ivl` (parse/elab/codegen) → VVP output.

```text
iverilog [-g2012] -o <run>.vvp -s <top> [-f <filelist>] [-D...] [-I...] <sources...>
```

- **`-o <file>`** — VVP output (default `a.out`). Vking should always set an explicit path under the run manifest artifact dir.
- **`-s <topmodule>`** — root module for elaboration (TB top). Required when auto root detection picks wrong module.
- **`-g2012`** — SV-2012 generation flag; Vking uses this for DUT capability probing (§4.3). Default generation is `-g2005` if omitted.
- **`-f` / `-c <cmdfile>`** — filelist/command-file ingestion (`+incdir+`, `+define+`, `+timescale+` tokens supported).
- **`-V`** — print version and exit (`Icarus Verilog version X.Y (tag)`). Use in `vking doctor` and run manifest `backend_version`.
- **`-t vvp`** — default target; only target Vking needs for simulation.

Elaboration is not a standalone CLI mode. The driver runs full compile; elab failures return non-zero via `t_compile()` → `ivl` exit status. **`-N <path>`** dumps post-elab netlist for debug only — not a gate hook.

### 2. `vvp` — simulation runtime (`vvp/main.cc`)

Primary subprocess for **ISimBackend.run** and **G2/G3** simulation.

```text
vvp [-n] [-l <log>] <run>.vvp [-fst] [+plusargs...]
```

- **`-n`** — non-interactive: `$stop` acts like `$finish` (CI/gate-friendly).
- **`-N`** — like `-n` but exit code 1 on `$stop` (testbench failure signaling).
- **`-l -`** — log to stderr (capture sim transcript in gate logs).
- **`-V`** — runtime version string for manifest.

On Unix, `iverilog` output may be a `#!…vvp` executable (`tgt-vvp/vvp.c`), but Vking should **always invoke `vvp <file>.vvp` explicitly** — especially on Windows/MinGW where shebang execution is unreliable.

### 3. Elaboration (in-process via compile, not a third binary)

G1.5 is satisfied by the same `iverilog` invocation as G1. The elaboration pipeline (`elaborate.cc`, `elab_sig.cc`) runs inside `ivl` before VVP codegen. Vking does **not** shell out to `ivl` directly — the `iverilog` driver is the stable contract.

### 4. Waveform dumper selection — extended args after `.vvp`

`$dumpfile` / `$dumpvars` in generated TBs; dumper format is selected by **extended arguments placed after the `.vvp` filename** (parsed by `system.vpi` via `vpi_get_vlog_info`, `vpi/sys_table.c`):

```text
vvp <run>.vvp -fst
```

Per §6.1 style law #8: always emit dump calls; pass **`-fst`** so GTKWave opens FST, not default VCD.

### 5. Version probe (doctor + manifest)

```text
iverilog -V
vvp -V
```

Both print `VERSION` + `VERSION_TAG` and exit 0. Record verbatim in `run_manifest.backend_version`.

## Quirks / flags / gotchas

### FST waveforms

- **`-fst`** (and `-fst-speed`, `-fst-space`, variants) are **extended args after the `.vvp` file**, not `vvp` getopt flags.
- FST support requires **zlib** at iverilog build time (`HAVE_LIBZ` in `vpi/sys_table.c`). Builds without zlib exit with `FST support disabled since zlib not available` — oss-cad-suite builds include it; bare installs may not.
- Default dumper is **VCD** (`IVERILOG_DUMPER` unset). Vking must pass `-fst` every sim run; do not rely on env alone.
- `IVERILOG_DUMPER=fst` env var is an alternative but extended `-fst` arg overrides per `sys_table.c` scan order.

### Timescale

- Compiler default before any `` `timescale `` is **1s/1s** (`+timescale+` in cmdfiles, `iverilog.man.in`).
- **`-Wtimescale`** warning class exists; mismatched/missing timescales across modules produce warnings (not always hard errors).
- Vking style law #1: every generated file carries explicit `` `timescale ``; runner must keep TB/DUT timescale consistent. VVP reads compiled `.timescale` directives into scopes (`vvp/vpi_scope.cc` `compile_timescale`).
- **`-T min|typ|max`** on `iverilog` selects min:typ:max delay corner (suppresses default-to-typ warnings).

### GPL subprocess boundary

- Icarus is **GPL-2.0**. Vking (Apache-2.0/MIT) must **only subprocess-invoke** installed `iverilog`/`vvp` — never link libivl/libvvp into Vking binaries, never ship GPL simulator artifacts in a Vking installer.
- `vking doctor` detects tools on PATH; points users to **oss-cad-suite** when missing (bundles iverilog+vvp+gtkwave, GPL kept outside Vking distribution).

### 4-state / G2 semantics

- VVP uses **4-state** (`x/z`) logic throughout (`vvp/resolv.h`, `verinum`). This is why **G2 is pinned to Icarus** — Verilator's 2-state lane makes X checks vacuous.
- Do not pass **`-gno-xtypes`** unless intentionally narrowing types; default is `-gxtypes` (extended types enabled).

### Language / profile constraints

- **Profile A (V2005-safe)** is the Icarus+Verilator intersection. **Profile B (SV-TB / concurrent SVA)** is **not** on Icarus — `-gassertions` elaborates only supported immediate/assertion subsets; concurrent SVA is Verilator-only per §4.3.
- Capability matrix probe: `iverilog -g2012` trial compile per module; if fail → Icarus-only gates report `N/A (backend unsupported)`, never silently skip.
- **`-gspecify`** / **`-ginterconnect`** off by default (RTL sim performance); enable only for timing/SDF lanes (Stage S4).

### Platform / invocation

- **Windows/MinGW**: `iverilog` `t_compile()` returns raw exit status on MinGW (differs from POSIX `WEXITSTATUS` path). Always use explicit `vvp file.vvp`.
- **`-v` on compile** embeds verbose flag in shebang — prefer separate `vvp` invocation for predictable logging.
- Exit codes: compile errors → non-zero from `iverilog`; sim failures → TB `$finish` / `vvp -N` / assertion failures in stdout/log (parse gate output from `-l` log).

### Not load-bearing for Vking v0.x

- Other targets (`-tblif`, `-tvhdl`, `-tvlog95`, …), `iverilog-vpi` (VPI module build), `ivhdlpp`, interactive `vvp` debugger shell, SDF annotate (`-sdf-*` extended args) — defer to Stage S4+ unless gate-level lane is active.

## Minimal gate/run recipe

```text
# G1 + G1.5 (compile + elab)
iverilog -g2012 -o <artifacts>/<run_id>.vvp -s <tb_top> -f <filelist.f>
# G2 + sim + FST waves
vvp -n -l <artifacts>/<run_id>.log <artifacts>/<run_id>.vvp -fst
```

Record in run manifest: `backend=iverilog`, `backend_version` from `-V`, `flags` including `-g2012` and `-fst`, `artifact_paths.waves` pointing at `$dumpfile` target.
