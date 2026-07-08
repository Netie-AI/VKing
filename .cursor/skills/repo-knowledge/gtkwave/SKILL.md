---
name: gtkwave-repo-knowledge
description: Load-bearing capability card for gtkwave — populated by repo-surveyor subagent. What Vking's frozen interfaces (§4.4) need from gtkwave.
---

# gtkwave — capability card

## Identity

| Field | Value |
|-------|-------|
| **What** | GTK+ waveform analyzer for Verilog simulation dumps (VCD/EVCD, FST, GHW) and `.gtkw` save files |
| **Upstream** | https://github.com/gtkwave/gtkwave |
| **Pinned commit** | `7d7b4db9e2f5485afe2aeeab0ad112f5b6a9b94b` (`nightly-353-g7d7b4db`, "Fix build on Hurd (#510)") |
| **Version in tree** | `4.0.0-prealpha` (`meson.build`) |
| **License** | GPL-2.0-or-later (`LICENSE`, `meson.build`) |

Vking never embeds or vendors GTKWave. Invoke the `gtkwave` binary as a subprocess (same rule as Icarus/Verilator in master plan §10). Custom in-app waveform viewing is forbidden until Stage 2 delta tracer exists (§9).

## Vking interface mapping

| §4.4 interface | How gtkwave is used |
|----------------|---------------------|
| **`IUIRenderer`** | Primary. v0.1 UI button **"Open waves in GTKWave"** spawns `gtkwave <wave_path>` using `artifact_paths.waves` from the run manifest. Fire-and-forget GUI process; no IPC required in v0.1. |
| **`ISimBackend` / `ITBGenerator`** | Indirect. TB codegen emits `$dumpfile` / FST via `vvp -fst`; sim writes the dump file GTKWave reads. Wave path must land in manifest before UI launch. |
| **`IGateRunner`** | Indirect. Gates G0–G3 do not invoke GTKWave; only successful runs with a wave artifact enable the UI action. |
| **Others** | No load-bearing coupling. |

## Load-bearing entry points (only these matter)

### 1. `gtkwave` CLI — subprocess launch (`src/main.c`)

The v0.1 integration surface. Positional form:

```text
gtkwave [DUMPFILE] [SAVEFILE] [RCFILE]
```

Equivalent flags: `-f/--dump=FILE`, `-a/--save=FILE`, `-r/--rcfile=FILE`.

Vking's minimal launch:

```text
gtkwave /path/to/run.waves
```

Optional later: pass a project `.gtkw` save as second positional arg to restore signal selection/zoom (not required for v0.1).

### 2. `-V/--version` — toolchain probe (`src/main.c` `print_help`, case `'V'`)

Used by `vking doctor` PATH detection. Banner format:

```text
GTKWave Analyzer v<PACKAGE_VERSION> (<VCS_TAG>) (w)1999-2022 BSI
```

Expect version skew vs this pinned tree: oss-cad-suite often ships GTKWave 3.x while `repos/gtkwave` tracks 4.0.0-prealpha. Doctor should accept any working `gtkwave` on PATH, not require this commit's build.

### 3. Dump loaders — wave file formats (`src/dump_file_main.c`, `gw-vcd-loader`, `gw-fst-loader`, `gw-ghw-loader`)

What Vking sim output must produce:

| Format | Vking relevance | Notes |
|--------|-----------------|-------|
| **FST** | Preferred for Icarus (`vvp -fst`) | Supports `-s/--start`, `-e/--end` time skip on load |
| **VCD/EVCD** | Fallback / legacy | Whole file loaded; gzip/zip OK per help text |
| **GHW** | GHDL flows (out of v0.1 scope) | gzip/bzip2 OK |
| **`.gtkw` save** | Optional UX enhancement | Can embed dump path; loadable as sole positional arg |

FST/LXT must stay **uncompressed** for random access (help text in `print_help`).

### 4. `.gtkw` save files — signal layout persistence (`src/main.c` ~1265+, save-file extract logic)

Save files record which traces are displayed, radix, markers, zoom. Vking may generate or ship template save files later; v0.1 only needs the raw dump path. A save file passed as `[SAVEFILE]` overrides display state on open.

### 5. WCP — Waveform Control Protocol (`src/wcp_gtkwave.c`, `lib/libwcp/`, `--wcp` flags)

JSON-over-TCP automation (default port **8765**). Commands include `add_items`, `set_viewport_to`, `add_markers`, `reload`; events include `waveforms_loaded`. Reference smoke test: `tools/wcp-smoke.sh`.

**Not for v0.1.** Reserved for post–Stage-2 programmatic control if Vking ever drives GTKWave instead of only launching it. Requires explicit `--wcp` (and optionally `--wcp-port=PORT`, `--wcp-remote`).

## Quirks, flags, and gotchas

1. **GPL subprocess only** — Never link libgtkwave into Vking or ship the binary inside Vking packages. Subprocess invocation preserves Vking's Apache-2.0/MIT license (§10).

2. **GUI requires a display** — GTK+3 application. `vking regress` / CI must **not** spawn GTKWave. Wave viewing is interactive-only via `IUIRenderer`.

3. **Headless flags are not a viewer** — `-x/--exit` loads then exits (benchmark loader). `-n/--nocli` opens a file picker (needs display). Neither replaces the v0.1 launch pattern.

4. **Platform flag gaps** — `-o/--optimize` (VCD→FST recode on load) is **disabled on MinGW/Windows** (`print_help` `#ifdef`). Do not rely on it in cross-platform Vking flows.

5. **WCP enable gate** — Server starts only when `--wcp` is passed (`wcp_enable` in `main.c`). Setting `--wcp-port` alone does not start the server.

6. **Manifest path contract** — `IUIRenderer` must use absolute or cwd-stable paths from `artifact_paths.waves`. GTKWave exits on load failure (`dump_file_main.c` → `exit(EXIT_FAILURE)`).

7. **No in-app viewer in v0.x** — Master plan §9: launching GTKWave is the entire waveform story until Stage 2 delta tracer + custom viewer. Do not plan WebGL/canvas wave rendering in v0.1 UI.

8. **Tcl automation exists but is not v0.1** — Embedded `gtkwave::addSignalsFromList` etc. (`docs/tcl/commands.md`) and WCP are for future deep integration; v0.1 is dump-file subprocess only.

9. **Deprecated pipe viewer** — `shmidcat … \| gtkwave -v` interactive VCD (`docs/ui/extras.md`) marked deprecated for GTKWave 4; ignore for Vking design.

## Minimal Vking contract (v0.1)

```text
# doctor
gtkwave -V

# after sim PASS, from run manifest artifact_paths.waves
gtkwave <absolute_path_to.fst_or.vcd>
```

Provenance: record detected `gtkwave -V` banner in run manifest `{backend, version, flags}` when the user opens waves (optional but aligns with §4.3 labeling).
