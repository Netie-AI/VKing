---
name: yosys-repo-knowledge
description: Load-bearing capability card for yosys — populated by repo-surveyor subagent. What Vking's frozen interfaces (§4.4) need from Yosys.
---

# yosys — capability card

## What it is

**Yosys** (Yosys Open SYnthesis Suite) is an RTL synthesis framework: read HDL → internal RTLIL → scripted passes → emit gate-level Verilog (or other backends). Vking is **not** a synthesis tool; Yosys appears only on the **S4 gate-level/timing lane** (`IGateRunner`): RTL → Yosys → OpenSTA → SDF → `$sdf_annotate` on Icarus. **S5 formal** uses **SymbiYosys (`sby`)** from the same OSS CAD Suite bundle — a separate front-end that shells out to the `yosys` binary; not on the v0.1–v0.5 critical path.

**Distribution (§10):** Vking does not bundle Yosys. `vking doctor` points missing simulators at **YosysHQ OSS CAD Suite** (Linux/macOS/Windows archive: `iverilog`, `vvp`, `verilator`, `gtkwave`, **plus SymbiYosys for formal later**). Invoke Yosys as a **subprocess**; ISC license keeps Vking's own license independent (same pattern as GPL simulators).

**CMake version (source tree):** `0.66` (`cmake/YosysVersionData.cmake`).

**Pinned commit:** `95b5e436050c6e546c2a09e1438fceb8d0a472e7` — merge of PR #6008 (sv-elab bump), 2026-07-07. Remote: `https://github.com/yosyshq/yosys.git`.

**License:** **ISC** (`COPYING`) — GPL-compatible, permissive. Bundled **ABC** (`abc/` submodule) and libs under `libs/` carry their own licenses; do not assume a single SPDX for the whole tree.

**Build notes (if compiling):** C++20, CMake ≥3.28, `git submodule update --init` (abc, slang, sv-elab, …). Produces `yosys`, bundled `yosys-abc`, and `yosys-config` (`misc/yosys-config.in`).

---

## Load-bearing entry points (§4.4)

Only what Vking's frozen interfaces need. Ignore FPGA `synth_*` flows, SMT/BTOR backends, plugins, and the interactive REPL unless debugging.

### 1. `yosys` CLI driver — subprocess invocation (`IGateRunner`)

**Path:** `repos/yosys/kernel/driver.cc` (`main`).

**Contract:** Headless batch use:

```text
yosys -Q -l run.log -p "read_verilog -sv …; hierarchy -check -top TOP; …; write_verilog netlist.v"
# or
yosys -Q -s gate.ys
```

| Flag | Vking use |
|------|-----------|
| `-Q` | Suppress banner (parse-friendly logs) |
| `-p "cmd1; cmd2"` | Inline script; **semicolon must be followed by whitespace** |
| `-s script.ys` | Script file (preferred for reproducible manifests) |
| `-r TOP` / `hierarchy -top TOP` | Elaborate top from `vking.toml` |
| `-D NAME[=VAL]` | Verilog defines → forwarded to `read_verilog` |
| `-o outfile` | Shorthand backend write on exit |
| `-V` / `--git-hash` | Version probe for `vking doctor` (S4+) |
| `-q` / `-e` | Quiet; promote warnings matching regex to errors |

**Failure semantics:** `log_error` → `_exit(1)` (`kernel/log.cc`). Treat nonzero exit as fail-closed for `IGateRunner`.

### 2. `read_verilog` — ingest `vking.toml` sources (`IGateRunner` input)

**Path:** `repos/yosys/frontends/verilog/verilog_frontend.cc` (frontend name `verilog`; command `read_verilog`).

**Contract:** Load RTL into current design. Multi-file: one `read_verilog` per file, or `read_verilog_file_list` for `.f` lists.

**Vking-relevant flags:**

- `-sv` — SystemVerilog (slang/sv-elab path; **synthesizable subset only**, IEEE 1800-2017/2023 informal)
- `-lib` — blackbox cell Verilog (companion to liberty stdcells)
- `-I dir` / `-D macro` — include dirs and defines (mirror `vking.toml` `[sources]`)
- Implicit `-D SYNTHESIS` unless `-nosynthesis` / `-formal`

**Mapping:** Emit a Yosys script from `vking.toml` `[sources]` (files, `include_dirs`, `defines`, `top`) — do **not** duplicate elaboration in pyslang for the gate lane; OpenSTA needs Yosys-elaborated netlist.

### 3. `synth` + liberty techmap — RTL → stdcell gate netlist (`IGateRunner` core)

**Paths:**

- `repos/yosys/techlibs/common/synth.cc` — `synth` (generic script: `hierarchy` → `proc` → `opt` → `memory` → `techmap` → `abc`)
- `repos/yosys/frontends/liberty/liberty.cc` — `read_liberty` (optional `-lib` blackboxes)
- `repos/yosys/passes/techmap/dfflibmap.cc` — `dfflibmap -liberty <file>`
- `repos/yosys/passes/techmap/abc.cc` — `abc -liberty <file>`

**Reference flow (S4):** `repos/yosys/examples/cmos/counter.ys`:

```text
read_verilog design.v
read_verilog -lib cells.v          # optional sim/cell wrappers
synth -top TOP                   # or: proc;; memory;; techmap;;
dfflibmap -liberty cells.lib
abc -liberty cells.lib
write_verilog synth.v
```

**Vking mapping:** `IGateRunner` must supply a **Liberty + companion cell library** (project-specific or documented golden). Default `synth` alone emits **generic `$`-cells / LUT mapping**, not OpenSTA-ready stdcells — **always** run `dfflibmap` + `abc -liberty` (or a documented `synth_*` + liberty variant) before `write_verilog`. Yosys does **not** write SDF; OpenSTA consumes the netlist + same liberty.

### 4. `write_verilog` — gate netlist artifact for OpenSTA + Icarus (`IGateRunner` output)

**Path:** `repos/yosys/backends/verilog/verilog_backend.cc` (backend `verilog`).

**Contract:** `write_verilog [options] [filename]`

**Vking-relevant flags for gate sim:**

- `-noattr` — drop Yosys attributes (cleaner for Icarus)
- `-simple-lhs` — simpler port connections
- `-noexpr` — emit cell instances instead of inline expressions (typical post-`abc` netlists)
- Avoid `-sv` unless downstream requires SV syntax; Verilog-2005-ish output is safer for Icarus gate sim

**Downstream:** OpenSTA reads this netlist + liberty → SDF → Icarus `$sdf_annotate` (see OpenSTA capability card).

### 5. `hierarchy` — top selection and elaboration checks (`IGateRunner`)

**Path:** `repos/yosys/passes/hierarchy/hierarchy.cc`.

**Contract:** `hierarchy -check [-top <module> | -auto-top]`

**Vking mapping:** Bind `vking.toml` `[project].top` here before synthesis. Catches missing modules / multiple tops early. `synth -top X` runs an equivalent check internally, but explicit `hierarchy` keeps manifest scripts readable.

---

## Quirks / gotchas

1. **Not on the v0.1–v0.3 path.** No Yosys hook in `ISimBackend`, `ITBGenerator`, or G0–G3. Only `IGateRunner` (S4) and later formal via **`sby`**, not raw Yosys passes.

2. **SDF is not Yosys's job.** S4 chain is Yosys → **OpenSTA** → SDF. Do not search Yosys for `write_sdf`; timing annotation is downstream.

3. **Liberty mapping is mandatory for real stdcells.** `synth` without `dfflibmap`/`abc -liberty` produces internal `$` gates unsuitable for OpenSTA stdcell timing. Pin the liberty file path in the run manifest.

4. **SV subset ≠ pyslang/Verilator subset.** Yosys accepts a **synthesizable** SV slice via slang/sv-elab; constructs valid in Vking RTL sim may fail synthesis. Gate lane needs its own capability matrix entries (`N/A` + honest banner).

5. **`-p` chaining syntax.** Commands in `-p` must use `; ` (semicolon + space). `cmd1;cmd2` can mis-parse.

6. **OSS CAD Suite vs Tabby.** README distinguishes Tabby (commercial parsers) from OSS CAD Suite. OSS builds use open `read_verilog`/slang — **not** the optional Verific frontend (`frontends/verific/`). Do not assume VHDL or industry SV parsers in the free bundle.

7. **Bundled ABC.** `abc` pass invokes `<bindir>/yosys-abc` unless `-exe` overrides. `IGateRunner` must put OSS CAD Suite `bin/` on PATH so both `yosys` and `yosys-abc` resolve.

8. **Cell simulation models.** Gate-level Icarus sim often needs `read_verilog -lib` for liberty cell Verilog (or `yosys-config --datdir/.../cells_sim.v` for FPGA libs). Vking must ship or reference these alongside the mapped netlist.

9. **`vking doctor` scope today.** §10 lists OSS CAD Suite for simulators + SymbiYosys; early `doctor` checks `iverilog`, `vvp`, `verilator`, `gtkwave` only. Add `yosys -V` / `sta` probes when S4 lands — do not block v0.1 on Yosys presence.

10. **Formal (S5) is SymbiYosys.** Tests call `${SBY} --yosys ${YOSYS}` (`tests/sva/runtest.sh`). Formal gates need **`sby`** + compatible Yosys version, not ad-hoc `read -formal` scripts alone.

11. **Fail-closed on errors.** Rely on process exit code, not log scraping alone; warnings can be promoted with `-e <regex>`.

12. **Submodules must be initialized** for a from-source build (`abc`, `slang`, `sv-elab`). A shallow clone without submodules will not compile — irrelevant if using OSS CAD Suite binaries.

---

## Vking interface map (quick reference)

| Vking interface | Yosys surface | Vking stage |
|-----------------|---------------|-------------|
| `IGateRunner` | `yosys -Q -s …` script: `read_verilog` → `hierarchy` → `synth`/techmap → `dfflibmap`/`abc -liberty` → `write_verilog` | S4 |
| `IGateRunner` (formal) | **`sby`** (SymbiYosys) with `--yosys` pointing at same binary | S5 |
| `vking doctor` / §10 | Detect or document OSS CAD Suite; optional `yosys -V` when S4+ | S4+ |

**Do not wire Yosys into:** `IHdlFrontend` (pyslang), `IProtocolDetector`, `ITBGenerator`, `IRtlGenerator`, `ISimBackend` (direct), `IMemoryStore`, `IUIRenderer` — no load-bearing hooks in v0.1–v0.5.
