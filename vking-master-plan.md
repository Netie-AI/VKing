# Vking — Master Plan

**Positioning:** Vking is a local Verilog/SystemVerilog verification workbench: it compiles, simulates, generates, and gates HDL on your own machine with no license server and no cloud dependency. It orchestrates proven open-source engines (Icarus Verilog, Verilator, slang) behind one interface and adds what they don't have — protocol-aware testbench generation, an RTL block generator, fail-closed verification gates with provenance, and (long-term) delta-cycle-accurate tracing that commercial tools charge for.

**Phrasing rule for interviews/README:** say "orchestrates iverilog and Verilator" — never "I wrote a compiler." The novel IP is the generation + gating + provenance + (later) delta-tracer layers, and that's a stronger claim because it's defensible.

**Plan status:** v1.0 · supersedes the earlier 8-layer/8-stage documents. Key structural change: the tool ships **usable-first** — a working vertical slice with a basic UI exists by ~day 4, and every subsequent version upgrades a module behind a stable interface rather than adding a dead layer.

---

## 1. Product definition

**What it is:** a single local app (CLI + local web UI) that, given Verilog/SystemVerilog RTL:
1. Parses and inventories it (ports, parameters, hierarchy, per-backend compilability).
2. Detects the interface protocol (AXI4-Lite/AXI4/APB/FIFO/handshake/SRAM/custom) with human confirmation.
3. Generates a self-checking testbench (deterministic templates first; LLM-assisted later).
4. Generates implementation RTL from a parameterized block catalog (FIFOs, synchronizers, arbiters, register blocks) — each block paired with its own testbench.
5. Runs everything through fail-closed gates on real simulators and reports honest, backend-labeled results.
6. Remembers verified facts about your modules with strict provenance, so results compound instead of being redone.

**What it is not (non-goals):**
- Not a simulator kernel (Stage 8 decision rule below; default outcome is "never build it").
- Not a synthesis or P&R tool (Yosys is invoked later only for gate-level sim prep).
- Not a claim of functional correctness: gates 0–3 prove *alive and self-consistent*; only golden-model comparison (G4) touches intent. The UI must say so.
- Not a waveform viewer in v0.x — Vking launches GTKWave; a custom viewer arrives only with the Stage-2 delta tracer that justifies it.

**Primary user (now):** you — generating TBs and standard RTL blocks fast, doubling as RTL/SoC interview drill. **Users (later):** small teams / open-source RTL projects wanting a free local verification workflow with CI integration.

---

## 2. Use cases (each maps to a shipped version)

| # | Use case | Available in |
|---|----------|--------------|
| UC1 | "Here's my module → give me a compiling, self-checking TB + Makefile in under a minute" | v0.1 |
| UC2 | "Generate a parameterized async FIFO / APB reg block / arbiter *with its TB*, ready to drop into a project" (Verilog-2005 and SV output flavors) | v0.2 |
| UC3 | "Lint + fast regression across my project, fail CI on gate failure" | v0.2 |
| UC4 | "Is this port bundle really AXI4-Lite? Prove conformance, don't just pattern-match" | v0.3 |
| UC5 | "LLM, propose stimulus/assertions for this weird custom interface — under gates" | v0.5 |
| UC6 | "Show me delta-cycle expansion / reconstructed AXI transactions like Vivado does" | v1.0+ |

---

## 3. Delivery model — ship-usable versions, not layers

Each version is independently useful; each upgrades one module behind an existing interface.

| Version | Timeline | You can now… | What's real vs. stubbed |
|---------|----------|--------------|--------------------------|
| **v0.1 — Vertical slice** | days 1–4 | UC1 end-to-end via CLI + one-page UI | Real: pyslang ingestion, signature-table detection, 3 TB templates, Icarus runner, gates G0–G2, run manifest, GTKWave launch. Stubbed: memory (SQLite file exists, minimal writes), Verilator lane, LLM, KG. |
| **v0.2 — Daily-driver** | days 5–14 | UC1 + UC2 + UC3 | Real: Verilator lint/regress lane, backend capability matrix, RTL block catalog (6 blocks + paired TBs), AXI4-Lite template, vacuity counters (G3-lite), SQLite memory with provenance column, `vking regress` CI mode. |
| **v0.3 — Trustworthy detection** | post-interview, ~2–4 wks | UC4 | Conformance-assertion gate for protocol facts; waiver system; full G3 (assertions + coverage floor); AXI4-full + APB templates; project memory queries in UI. |
| **v0.4 — Memory that compounds** | +2–4 wks | retrieval-assisted generation | Hybrid BM25+dense retrieval over verified artifacts only; provenance levels enforced end-to-end; labeled-module corpus export (feeds v0.6 KG). |
| **v0.5 — LLM under gates** | +3–5 wks | UC5 | LLM path enters as **cocotb Python** generation (not more Verilog codegen), constrained schema, self-consistency N=3, bounded repair ≤3, all output re-gated G0–G2 before display. |
| **v0.6 — KG earns its slot** | when corpus ≥ ~50 confirmed modules | better ambiguous-case detection | LightMa-style graph trained on Vking's own labeled corpus; must beat the signature table on a held-out set or it doesn't ship. |
| **v0.7 — UI, the real one** | parallelizable | dense dark data panels + glass chrome | Palantir-style panels for RTL/TB/gate/KG views; glass strictly on nav/palette/overlays; command-palette navigation. |
| **v1.0 — Vivado-parity debug** | long-term | UC6 | Stage-2 VPI delta tracer + delta-indexed trace format + viewer; Stage-3 AXI transaction reconstruction. |
| **v1.x — Depth** | long-term | timing sim, formal | Yosys→OpenSTA→SDF→`$sdf_annotate` gate-level lane; SymbiYosys formal gate; Stage-8 kernel decision (default: don't). |

---

## 4. Architecture (revised)

```
UI (v0: one dark page · v0.7: dense-core + glass-chrome)
        ↑
Gates G0–G4 (split policy: fail-closed on GENERATED artifacts,
             advisory+waivers on USER RTL) + run manifest
        ↑
Sim backends behind ISimBackend + BackendPolicy matrix
   iverilog  = 4-state, event/delta-accurate reference lane
   Verilator = lint, throughput, coverage lane (2-state)
        ↑
Generators behind ITBGenerator / IRtlGenerator
   deterministic templates (JSON schema → Verilog codegen)
   RTL block catalog (parameterized, TB-paired)
   [v0.5] LLM → cocotb Python (schema-constrained, gated)
        ↑
Memory/provenance behind IMemoryStore (SQLite → hybrid retrieval)
        ↑
Protocol detection behind IProtocolDetector
   v0: signature tables + structural scoring   [v0.6: KG]
        ↑
Ingestion behind IHdlFrontend: pyslang (elaboration-capable)
        ↑
Project manifest: vking.toml (filelists, includes, defines, top)
```

### 4.1 The IR — the real coupling point
The IR carries **two views per module**, because detection and generation need different things:
- **Generic view:** module name, port list (name/dir/declared width expr), parameter list, raw source span. Used by detection and the UI port table.
- **Elaborated view:** per chosen top + parameter set, concrete widths, resolved hierarchy (from pyslang elaboration). Used by TB generation and gate runs.

Every elaborated artifact records its parameter set; a TB is valid only for the parameterization it was generated against. Parameter sweeps are a first-class run type later, not an afterthought.

### 4.2 Language subset policy (the #1 architectural risk, handled explicitly)
Generated testbenches target a declared **dialect profile**:
- **Profile A — "V2005-safe"** (default): Verilog-2005 + immediate-assertion-style checks. Runs on *both* Icarus and Verilator. This is what templates emit in v0.x.
- **Profile B — "SV-TB"**: SystemVerilog TB constructs + SVA. Runs on the Verilator lane (and commercial sims); **not** on Icarus. Selectable per-generation from v0.2; becomes the default for SV-heavy DUTs later.
- **Profile C — "cocotb"** (v0.5+): TB logic in Python over VPI; DUT-language burden only. This is the LLM target.

DUT side: at import, Vking **probes compilability per backend** (`iverilog -g2012` trial compile; `verilator --lint-only`) and stores a capability matrix per module. The UI shows it. If a DUT compiles only under Verilator, the Icarus-only gates are reported as `N/A (backend unsupported)` — never silently skipped, never faked.

### 4.3 Backend policy matrix (hard rules, enforced by the runner)

| Job | Backend | Why |
|-----|---------|-----|
| Lint (G0 on generated code; advisory on DUT) | Verilator `--lint-only -Wall` | best lint in OSS |
| X/reset sanity (G2) | **Icarus only** | Verilator 2-state makes G2 near-vacuous |
| Delta-level debug, glitch investigation | Icarus (+ Stage-2 VPI tracer later) | event-accurate scheduler |
| Regression throughput, coverage | Verilator (`--coverage`) | speed; line/toggle coverage |
| SVA-based assertion runs (Profile B) | Verilator | Icarus lacks concurrent SVA |
| Golden-model comparison (G4) | same backend + seed for both runs | comparability |

Every result artifact carries `{backend, version, flags, seed, timescale, dialect_profile}`. The UI never renders an unlabeled PASS.

### 4.4 Interfaces (frozen signatures early, implementations swappable)
`IHdlFrontend`, `IProtocolDetector`, `ITBGenerator`, `IRtlGenerator`, `ISimBackend`, `IGateRunner`, `IMemoryStore`, `IUIRenderer`. Rule: a version may replace at most the internals behind one or two interfaces; interface changes require a written migration note in `CHANGES.md`. This is what keeps "modular and improving" true instead of aspirational.

---

## 5. Protocol detection — v0 spec (signature tables), KG later

**v0 mechanism:** YAML signature tables + deterministic scoring. No graph, no learned weights, no spreading activation.

```yaml
# signatures/axi4lite.yaml
protocol: AXI4-Lite
role_detect: {slave_prefixes: [s_axi, s00_axi, saxi], master_prefixes: [m_axi, m00_axi]}
required_groups:
  aw: [awvalid, awready, awaddr]
  w:  [wvalid, wready, wdata, wstrb]
  b:  [bvalid, bready, bresp]
  ar: [arvalid, arready, araddr]
  r:  [rvalid, rready, rdata, rresp]
forbidden: [awlen, awburst, arlen]   # presence ⇒ AXI4-full, not Lite
direction_rules: {slave: {awvalid: in, awready: out, ...}}
hub_tokens_ignored: [clk, clock, rst, rst_n, reset, resetn, data, en]
```

**Score = token-match ratio × structural completeness × direction consistency**, with:
- Missing any required group ⇒ confidence hard-capped at 0.5 (not merely reduced).
- Any `forbidden` token present ⇒ this signature is disqualified, sibling signature suggested.
- Hub tokens contribute zero score (they match everything).
- Prefix stripping is tried per `role_detect` list plus a generic `<word>_` strip pass.

**Thresholds & policy:**
- ≥ 0.85 → auto-suggest, one-click human confirm.
- 0.5–0.85 → show top-3 candidates + "custom".
- < 0.5 → default to custom/handshake template.
- **A protocol fact never enters memory without human confirmation** in v0.1–v0.2, and never reaches `verified` status without the **conformance gate** (v0.3): a small falsification assertion set (e.g., AXI: `valid && !ready |=> valid`; address stable while valid; APB: `PENABLE` only after `PSEL`) must pass against the DUT under template stimulus. Detection that merely pattern-matched is stored as `L0_hypothesis`, full stop.
- Confidence from a hand-written table is **decoration, not calibration** — the UI labels it "match score", not probability.

**KG upgrade criteria (v0.6):** activates only when the tool's own confirmed-module corpus ≥ ~50; trained graph must beat the signature table on a held-out split; falls back to tables on tie. This makes Vking bootstrap its own training data — the correct sequencing that the original plan inverted.

---

## 6. Generation

### 6.1 Testbench templates (deterministic, v0.1–v0.3)
Pipeline: elaborated IR + confirmed protocol → **JSON stimulus/assertion schema** (same schema the LLM will later have to emit — designed once, reused) → deterministic codegen → Verilog TB (Profile A) or SV TB (Profile B).

Template set: v0.1 = `clk_rst_smoke` (any module: clock/reset, drive-inputs-legal, watch outputs), `handshake_stream` (valid/ready), `sram_rw` (addr/we/din/dout, write-then-read scoreboard). v0.2 adds `axi4lite_slave`. v0.3 adds `axi4_full_slave`, `apb_slave`, `fifo`.

**Generated-TB style law** (non-negotiable, enforced by codegen unit tests — this is the anti-race, anti-vacuity, anti-backend-divergence layer):
1. Explicit `` `timescale `` in every generated file; runner passes matching flags to both backends.
2. Drive DUT inputs on `negedge clk` (or NBA with declared skew); sample/check on `posedge clk`. No blocking drives at posedge, ever.
3. No `#0`; no mid-cycle asynchronous checks on combinational nets.
4. Reset protocol: assert N cycles, release synchronously, X-check window starts M cycles after release.
5. Watchdog timeout with clear failure message; simulation can never hang silently.
6. **Vacuity counters:** every check maintains an antecedent-fired counter; end-of-sim report lists checks with count < N as `VACUOUS`.
7. Self-checking only — a TB that just wiggles pins is not a deliverable.
8. `$dumpfile/$dumpvars` (FST via `vvp -fst` on Icarus) always emitted; waveform path recorded in the run manifest.

### 6.2 RTL block catalog (v0.2) — the "generate code for implementation" requirement
Parameterized, synthesizable, emitted in **both** Verilog-2005 and SystemVerilog flavors, each shipping with its paired TB and run through the full generated-artifact gate chain before it's ever handed to the user:

`fifo_sync` (depth/width, first-word-fall-through option) · `fifo_async` (gray-coded pointers, 2FF sync, parameterized depth=2^N) · `cdc_sync_2ff` · `apb_regblock` (register map from a small YAML spec) · `rr_arbiter` · `skid_buffer` (valid/ready pipeline stage).

Dual purpose is explicit: these are the canonical RTL-interview blocks. Building/reviewing them *is* interview prep, which is the honest justification for the two-week spend.

### 6.3 LLM path (v0.5, not before)
- Target = **cocotb Python coroutines**, not Verilog. Rationale: Python is a dramatically better LLM-generation target to validate, constrain, and auto-repair; cocotb runs against both Icarus and Verilator over VPI/GPI, dissolving the TB-dialect intersection problem. (Correction to the earlier plan, which deferred cocotb to Stage 5 while proposing LLM→JSON→Verilog — backwards.)
- Harness: role-constrained system prompt (emit schema/coroutine only), retrieved context from **verified-only** memory slots, self-consistency N=3 keep-best-coverage-among-passers, bounded repair ≤3 fed with the *specific* gate failure, then human escalation. Every proposal re-runs G0–G2 before any human sees it. Every prompt/response/gate-result triple is logged with provenance `L0`.

---

## 7. Gates (revised spec)

**Split policy:** *Generated artifacts* (TBs, catalog RTL, codegen output): **fail-closed, no waivers.** *User RTL:* lint is advisory with a per-project waiver file (`vking-waivers.toml`); compile failures per backend are recorded in the capability matrix, not treated as tool errors.

| Gate | Check | Backend | Failure semantics |
|------|-------|---------|-------------------|
| **G0** | Lint clean (`verilator --lint-only -Wall`) | Verilator | Fail-closed for generated; advisory+waiver for DUT |
| **G1** | Compiles | per policy matrix | Fail-closed |
| **G1.5** | Elaboration/bind: top instantiates, no dangling/width-mismatched TB↔DUT connections | Icarus elab / pyslang | Fail-closed (catches most codegen bugs cheaply) |
| **G2** | Reset/X sanity: clock toggles, reset releases, watched outputs X-free after settle window | **Icarus, 4-state, always** | Fail-closed |
| **G3** | Checks/assertions pass **and are non-vacuous** (antecedent counters ≥ N); coverage ≥ floor (Verilator lane) | per profile | Fail-closed; `VACUOUS` is a distinct red state, never PASS |
| **G4** | Golden-model comparison | same backend+seed both runs | Optional; the only gate that speaks to functional intent |

**Run manifest (JSON, one per run, immutable):** `{run_id, timestamp, module, param_set, dialect_profile, backend, backend_version, flags, seed, timescale, gate_results{...}, vacuity_report, waivers_applied, artifact_paths{tb, filelist, waves, log}}`. This is the enforcement mechanism for §4.3's labeling rule and §8's provenance — not a convention.

**Honesty banner (UI + CLI summary):** "G0–G3 verify the testbench and DUT are alive and self-consistent. Functional correctness requires G4 or your own review." Green chips must never be paintable as "verified correct."

---

## 8. Memory & provenance

**v0.2 storage:** single SQLite DB. Tables: `modules(id, name, src_hash, capability_matrix, …)`, `runs(run_id, manifest_json)`, `facts(id, module_id, kind, body, provenance_level, source, evidence_run_id, created_at)`, `corrections(fact_id, human, note, at)`.

**Provenance levels (typed enum, required on every fact write):**

```
L0_hypothesis < L1_compiled < L2_sim_active < L3_assert_nonvacuous
             < L4_conformance_passed < L5_golden_matched
H_human_attested  (parallel class; challengeable by L4 conformance runs)
```

**Enforcement mechanisms (all four required — without them this is a comment, not a property):**
1. **Single write path:** only `IMemoryStore.write_fact()` writes; it refuses writes lacking a level or evidence pointer. No direct DB access from harness/UI code (enforced by module structure + a grep check in CI).
2. **Min-of-inputs propagation:** any derived/aggregated fact takes the *minimum* level of its inputs. Fact-extraction/summarization jobs cannot promote; "reused three times" never becomes "known pattern".
3. **Filtered retrieval slots:** few-shot/system-prompt slots draw from `L3+` only; `L0–L2` material may appear only in an explicitly labeled "unverified ideas" slot. Session→project archiving re-checks levels item-by-item; no bulk copy.
4. **"Gate-verified" is banned vocabulary** — facts state *which* level, because G0–G2 means *compiled/alive*, not *true*.

v0.4 adds hybrid BM25+dense retrieval (SkillMesh reuse) over `L3+` artifacts; the index stores the provenance level alongside every chunk so filtering happens at query time, not post-hoc.

---

## 9. UI

**v0.1 (one dark page, deliberately plain — no glass, no framework ceremony):** served locally by the same process as the CLI. Panels: (1) project/file picker reading `vking.toml`; (2) module + port table with per-backend capability chips; (3) protocol suggestion with match score + confirm/override dropdown; (4) Generate button (TB template or RTL block + parameters form); (5) gate status chips with drill-down to log excerpts and the honesty banner; (6) "Open waves in GTKWave" + "Download TB / filelist / Makefile". Stack: FastAPI + one HTML page + vanilla JS/htmx — no build toolchain in week one.

**v0.7 (the real UI, unchanged direction):** dense high-contrast dark panels (Palantir-Foundry register) for all data-dense views — RTL/TB code, gate matrix, memory/KG explorer, later waveforms; translucent glass strictly for nav, ⌘K command palette, overlays, toasts; **never on data panels**. Dark-first, light as secondary toggle. Command-palette navigation (jump-to-module / jump-to-failing-gate / jump-to-past-TB) over menu trees.

> **Glass, in plain words:** a soft frosted-glass blur — like light through foggy glass — used only on the floating top bar, the ⌘K search popup, and notification toasts; every screen showing real data (code, tables, gate results, waveforms, the KG) stays flat, solid, and dark for easy reading, with dark mode as the default and light mode an optional switch.

**Custom waveform viewer:** forbidden until the Stage-2 delta tracer exists to justify it; a viewer without delta data is a worse GTKWave.

---

## 10. Distribution, production & operations

- **Packaging:** Python ≥3.11, `pipx install vking` / `uv tool install vking`. Core deps: `pyslang`, `fastapi`, `uvicorn`, `pydantic` (schemas), `jinja2` (codegen), stdlib `sqlite3`.
- **Toolchain:** Vking does **not** bundle simulators. `vking doctor` detects `iverilog`, `vvp`, `verilator`, `gtkwave` on PATH; if missing, it points at the **YosysHQ oss-cad-suite** download (single archive, Linux/macOS/Windows, includes all four plus SymbiYosys for the later formal lane). This solves cross-platform install and keeps GPL binaries out of Vking's own distribution in one move.
- **Licensing:** invoking GPL tools (Icarus) as subprocesses keeps Vking's license independent — Apache-2.0 or MIT for Vking itself. Do not vendor simulator binaries into an installer.
- **Project manifest (`vking.toml`):**

```toml
[project]
name = "my_soc_block"
top = "sram_axi_wrapper"

[sources]
files = ["rtl/sram_axi_wrapper.sv", "rtl/sram_core.v"]
include_dirs = ["rtl/include"]
defines = { SIM = "1" }

[params.default]
ADDR_W = 12
DATA_W = 32
```

- **CI mode:** `vking regress --profile fast` — headless, Verilator lane, nonzero exit on any fail-closed gate failure, manifests emitted as artifacts. This is UC3 and the production credibility feature: a GitHub Actions snippet ships in the README.
- **Config precedence:** CLI flags > `vking.toml` > user config > defaults. All effective config echoed into the run manifest.
- **Versioning:** semver; interface changes documented in `CHANGES.md` per §4.4.

---

## 11. Dogfooding — testing Vking itself

- **Golden corpus** (grows over time, checked into the repo): your AXI/APB SRAM IP (the ground-truth seed), each catalog block, plus 5–10 small third-party open-source modules with deliberately awkward port naming (prefixes, `_n` suffixes, VHDL-converted styles) to exercise detection honestly.
- **Snapshot tests:** codegen output for fixed IR+schema inputs is byte-stable; any diff is a reviewed change.
- **Self-regression:** every catalog block's paired TB must pass G0–G3 on both applicable backends in Vking's own CI before release. The tool that gates other people's code gates its own.
- **Detection eval:** precision/recall of the signature tables on the corpus, tracked per release — this metric is also the tripwire for the v0.6 KG decision.

---

## 12. Risk register (top failure modes → standing mitigations)

| # | Risk | Mitigation (section) |
|---|------|----------------------|
| 1 | Backend language-subset divergence: TB runs on one engine, not the other | Dialect profiles + capability matrix + `N/A` reporting (§4.2) |
| 2 | Confidently-wrong protocol detection poisons memory | Human confirm + conformance gate before `verified` + L0 default (§5) |
| 3 | Vacuous assertion pass = false green | Antecedent counters, `VACUOUS` as distinct state (§6.1, §7) |
| 4 | Verilator 2-state masks X bugs | G2 pinned to Icarus 4-state (§4.3, §7) |
| 5 | TB race conditions pass locally, fail on commercial sims | Generated-TB style law, codegen unit tests (§6.1) |
| 6 | Provenance laundering via retrieval/summarization/archiving | Four enforcement mechanisms (§8) |
| 7 | Fail-closed lint rejects all real-world DUTs | Split gate policy + waiver file (§7) |
| 8 | Parameterized modules break templates | Dual-view IR; TB bound to param set (§4.1) |
| 9 | Multi-file projects unmanageable | `vking.toml` manifest from day one (§10) |
| 10 | Scope creep vs. interview prep | Cut order + hard DoD (§14); dual-use catalog (§6.2) |

---

## 13. Long-term roadmap (capability ladder, each stage gated by what it must prove)

| Stage | Deliverable | Entry criterion ("proved before") |
|-------|-------------|-----------------------------------|
| S1 | Foundation (v0.1–v0.3 above) | — |
| S2 | **VPI delta tracer**: Icarus scheduler hook emitting `(time, delta_idx, signal, value)`; delta-indexed trace format (superset of VCD/FST); viewer delta-expand mode. The genuinely novel IP. | v0.3 stable; users actually hitting delta-level debug needs |
| S3 | Protocol-aware transaction reconstruction (AXI bursts as labeled objects in the wave view) | S2 trace format exists; detection at `L4` reliability |
| S4 | Gate-level/timing lane: Yosys → OpenSTA → SDF → `$sdf_annotate` on Icarus | Netlist-sim demand demonstrated on a real project |
| S5 | Formal (SymbiYosys) + coverage-driven closure in gate criteria | G3 coverage floors meaningful on real projects |
| S6 | KG (LightMa reuse) replaces signature tables where it wins | Labeled corpus ≥ ~50; beats tables on held-out set (§5) |
| S7 | Full UI (dense core + glass chrome + custom viewer) | S2 delta data exists to display |
| S8 | Custom event-driven kernel — **decision, default no** | Only if S1–S7 surface concrete LRM/introspection/parallel-sim needs Icarus+VPI cannot meet. "Didn't need to build it" is the success case. |

---

## 14. Two-week execution plan (≈ 3–4 h/day alongside interview prep)

| Days | Deliverable | Done means |
|------|-------------|------------|
| 1 | Repo, interfaces frozen, `vking.toml` parser, `vking doctor`, pyslang ingestion → dual-view IR | `vking scan` prints module/port/param table for the SRAM IP |
| 2 | Signature tables (handshake, SRAM, AXI4-Lite recognizer-only) + scoring + CLI confirm flow | Correct top-1 on SRAM IP; sane "custom" fallback on a garbage-named module |
| 3 | Schema + codegen + `clk_rst_smoke` & `sram_rw` templates; Icarus runner; G0/G1/G1.5/G2; run manifest | `vking gen && vking run` produces PASS with waves on SRAM IP |
| 4 | One-page UI wired to the above; GTKWave launch; TB/Makefile download | **v0.1: someone else could use it** |
| 5–6 | Verilator lane (lint + fast run), capability matrix, `handshake_stream` template, waiver file | Both backends labeled in UI; DUT lint advisory works |
| 7–8 | `axi4lite_slave` template + vacuity counters (G3-lite) | AXI4-Lite TB passes non-vacuously on SRAM IP |
| 9–11 | RTL catalog: `fifo_sync`, `cdc_sync_2ff`, `apb_regblock`, `skid_buffer` (+`fifo_async`, `rr_arbiter` if on schedule), each with paired gated TB, both language flavors | Every shipped block green through G0–G3 on its applicable backends |
| 12 | SQLite memory + provenance column + single write path; `vking regress` CI mode | Facts written only via API with levels; CI snippet in README |
| 13 | Dogfood corpus + snapshot tests + detection eval numbers | Vking's own CI green |
| 14 | README (honest positioning per header), demo GIF, tag **v0.2** | Interview-ready artifact |

**If slipping, cut in this order:** `fifo_async`/`rr_arbiter` → `handshake_stream` template → UI polish beyond functional → memory layer (fall back to manifests-on-disk only) → Verilator coverage numbers. **Never cut:** the style law, the vacuity counters, G2-on-Icarus, the run manifest, the honesty banner — those are the difference between a tool and a demo that lies.

**Definition of done (2-week window):** v0.2 tagged; UC1–UC3 work end-to-end on the golden corpus; every claim in the README is demonstrable in under five minutes; and you stopped touching it to go prep FSM/CDC/FIFO interview questions — using the catalog blocks you just built as the drill set.
