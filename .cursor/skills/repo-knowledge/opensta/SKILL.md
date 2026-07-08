---
name: opensta-repo-knowledge
description: Load-bearing capability card for OpenSTA — populated by repo-surveyor subagent. What Vking's frozen interfaces (§4.4) need from OpenSTA.
---

# OpenSTA — capability card

**Status:** Surveyed 2026-07-08 · **Provenance:** L2_sim_active (repo read + commit pinned)

## Identity

| Field | Value |
|---|---|
| **What** | Gate-level **static timing analyzer (STA)**. Reads synthesized Verilog netlists + Liberty libraries + SDC constraints; computes delays/slacks; writes **SDF** for gate-level simulation. Tcl-driven CLI (`sta`) or embeddable C++ library (`libOpenSTA.a`). |
| **Pinned commit** | `4533a67a26c9dc02819800a6f9077f3020eaec58` (2026-07-06) — merge from `The-OpenROAD-Project-staging/sta_latest_0629` |
| **CMake version** | 3.1.0 (`project(STA VERSION 3.1.0)`) |
| **Remote** | `https://github.com/The-OpenROAD-Project/OpenSTA.git` (fork; upstream canonical repo is `parallaxsw/OpenSTA`) |
| **License** | **GPL-3.0** (dual-licensed commercially by Parallax Software; Vking must treat as GPL subprocess only, same rule as Icarus — §9) |
| **Binary** | `sta` (not `opensta`); built at `build/sta` |

## Vking interface mapping

| §4.4 interface | Role | Stage |
|---|---|---|
| **`IGateRunner`** | Primary consumer. Runs STA on Yosys-synthesized netlist, emits SDF, reports setup/hold pass-fail for gate-level lane. | **S4 / v1.x** — deferred; not needed for v0.x G0–G4 |
| **`ISimBackend`** | Downstream consumer of OpenSTA output: Icarus `$sdf_annotate` on the SDF file OpenSTA writes. | S4 chain: `Yosys → OpenSTA → SDF → Icarus` |

## Load-bearing entry points (5)

### 1. CLI subprocess — `sta -exit script.tcl`

`app/Main.cc` is the only integration surface Vking should use (GPL subprocess, no `libOpenSTA.a` linking).

```
sta [-help] [-version] [-no_init] [-no_splash] [-threads count|max] [-exit] script.tcl
```

- `-version` → prints `STA_VERSION` (for `vking doctor` / run manifest `backend_version`)
- `-exit` → non-zero exit on Tcl error (fail-closed gate hook)
- `-no_init` / `-no_splash` → headless CI use
- Exactly one positional `cmd_file` when batch-running; interactive REPL when omitted

### 2. Design ingest — `read_liberty` + `read_verilog` + `link_design`

Gate-level netlist from Yosys plus matching Liberty corner(s). `link_design <top>` is mandatory after `read_verilog`; without it STA has no linked network.

Typical Vking script head:

```tcl
read_liberty $LIBERTY
read_verilog $NETLIST
link_design $TOP
```

OpenSTA's Verilog reader is gate-level only (cell instances, nets, assigns) — not RTL synthesis. Yosys must run first.

### 3. Constraints — `read_sdc` or inline SDC Tcl

SDC is required for meaningful delay calculation. Without clocks/delays, `write_sdf` produces empty or default delays.

```tcl
read_sdc $SDC
# or inline:
create_clock -period 10 [get_ports clk]
set_input_delay  -clock clk 1.0 [all_inputs]
set_output_delay -clock clk 2.0 [all_outputs]
```

Vking must ship or generate a minimal SDC per design (see `examples/gcd_sky130hd.sdc`).

### 4. Timing analysis — `report_checks` / `check_setup`

Run analysis before exporting SDF. `report_checks` drives delay annotation; `check_setup` is the fail-closed preflight (unconstrained endpoints, missing clocks, loops).

```tcl
report_checks -path_delay max
report_checks -path_delay min
check_setup -verbose          # optional gate before SDF write
```

Parse stdout for slack PASS/FAIL; no JSON API exists.

### 5. SDF export — `write_sdf` (the S4 deliverable)

Primary artifact for `ISimBackend` / Icarus `$sdf_annotate`:

```tcl
write_sdf -no_timestamp -no_version -digits 6 -divider . $SDF_OUT
```

Key flags (from `search/SdfWriter.cc`, `search/test/search_write_sdf_model.tcl`):

| Flag | Purpose |
|---|---|
| `-no_timestamp` / `-no_version` | Deterministic SDF for snapshot/regression tests |
| `-digits N` | Delay precision (default varies) |
| `-divider .` or `/` | Hierarchy separator in SDF paths — must match Icarus netlist |
| `-include_typ` | Emit typ/min/max triples |
| `-scene <name>` | Multi-corner MCMM flows |

**Prerequisite:** `report_checks` must run first; `write_sdf` alone on an unanalyzed design is useless.

## Deferred / not load-bearing for v0.x

- **`libOpenSTA.a` C++ API** (`doc/StaApi.txt`, `search/Sta.cc`) — embeddable timing engine; Vking defers to Tcl subprocess per GPL policy.
- **SPEF/parasitics** (`read_spef`, `read_parasitics`) — post-route signoff; not needed for initial S4 lane.
- **Power** (`read_vcd`, `read_saif`, `report_power`) — out of scope.
- **Yosys `opensta` / `sdc_expand` passes** — live in `repos/yosys`, not here; they shell out to `sta` for SDC expansion only.

## Quirks / gotchas

1. **GPL subprocess only.** Never vendor or link `libOpenSTA.a` into Vking. Invoke `sta` as external process; record `{backend: "opensta", version: <STA_VERSION>, flags: ...}` in run manifest.

2. **Binary is `sta`, not `opensta`.** Yosys `opensta` pass defaults to `sta` (`yosys/techlibs/common/opensta.h`). `vking doctor` should probe `sta -version`.

3. **Not in oss-cad-suite v0 bundle.** Master plan lists iverilog/verilator/gtkwave in oss-cad-suite; OpenSTA is a separate build (CMake + CUDD + Tcl + SWIG). Timing lane is S4 — do not block v0.x on OpenSTA presence.

4. **Liberty + SDC are hard prerequisites.** Yosys netlist alone is insufficient. Vking's `IGateRunner` must thread PDK Liberty path and a generated/minimal SDC; missing constraints → `check_setup` warnings and meaningless SDF.

5. **Tcl-only, text output.** No stable JSON/structured report format. Vking must generate Tcl driver scripts and parse `report_checks` / `check_setup` stdout for gate results. Fail-closed on non-zero `sta -exit` exit code.

6. **Hierarchy divider must match downstream sim.** `write_sdf -divider` must agree with how Yosys names instances and how Icarus resolves `$sdf_annotate` paths. Mismatch = silent zero-delay or annotate failures.

7. **Fork vs upstream.** This tree tracks `The-OpenROAD-Project/OpenSTA`; README states `parallaxsw/OpenSTA` is canonical and forks may lack full regression. Pin commit for reproducibility.

8. **Build deps are heavy.** CUDD 3.0.0 (required), Tcl 8.6, SWIG, Bison/Flex, Eigen, fmt (if no C++20 `std::format`). Optional zlib for `.gz` Liberty/Verilog/SDF.

## Minimal S4 driver script (reference)

```tcl
# vking gate-timing lane (S4) — generated driver
read_liberty $::env(VKING_LIBERTY)
read_verilog   $::env(VKING_NETLIST)
link_design    $::env(VKING_TOP)
read_sdc       $::env(VKING_SDC)

report_checks -path_delay max
report_checks -path_delay min
check_setup -verbose

write_sdf -no_timestamp -no_version -digits 6 -divider . $::env(VKING_SDF_OUT)
```

Invoke: `sta -no_init -no_splash -exit /path/to/driver.tcl`

## Key source anchors

| Path | Why |
|---|---|
| `app/Main.cc` | CLI flags, exit codes, Tcl init |
| `search/Sta.cc` (`writeSdf`) | SDF writer entry |
| `sdf/SdfWriter.cc` | SDF format, version stamp, divider logic |
| `verilog/VerilogReader.cc` | Gate-level netlist ingest |
| `examples/sdf_delays.tcl`, `examples/gcd_sky130hd.sdc` | Canonical minimal flows |
| `search/test/search_write_sdf_model.tcl` | Regression reference for `write_sdf` flags |
