# Vking Prototype (v0.1)

Local one-page Verilog workbench: parse ports, generate a `clk_rst_smoke` testbench, compile and simulate with **Icarus Verilog**, and inspect gate results. This is a **prototype** — not a production release.

## Scope disclaimer

- Gates **G0–G3** prove the TB and DUT are alive and self-consistent; they do **not** prove functional correctness (see honesty banner in the UI).
- **G0** (Verilator lint) is **N/A** in this prototype.
- **G2** is pinned to **Icarus 4-state** per the master plan.
- Waveforms and the delta panel both use **VCD** in this prototype (GTKWave opens VCD). Reconstructed delta is **not** the Stage-2 VPI scheduler.
- Vking does **not** bundle simulators; you install toolchain binaries separately.

## Prerequisites

- **Python ≥ 3.11**
- **oss-cad-suite** (or equivalent) with `iverilog`, `vvp`, and `gtkwave` on `PATH`

### Install oss-cad-suite on Windows

Follow the [IEEE Columbus open-source IC tools guide](https://r2.ieee.org/columbus-ssccas/resources/open-source-ic-tools/) or:

1. Download the Windows `.exe` from [YosysHQ oss-cad-suite-build releases](https://github.com/YosysHQ/oss-cad-suite-build/releases/latest).
2. Run the installer — extract to **`C:\oss-cad-suite`** (no spaces in path).
3. User PATH should include `C:\oss-cad-suite\bin` and `C:\oss-cad-suite\lib` (Vking doctor prepends both automatically; you can also run `start.bat` from that folder).
4. Optional: set user env `OSS_CAD_SUITE=C:\oss-cad-suite`.
5. Open a **new** terminal and verify:

   ```powershell
   iverilog -V
   vvp -V
   yosys -V
   gtkwave -V
   ```

Or run `prototype/scripts/install_oss_cad.ps1` to download automatically.

If any command is missing, the UI still loads but **Run simulation** stays disabled until `iverilog` and `vvp` are found.

## Python setup

```powershell
cd prototype
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run the web UI

From the `prototype` directory (with venv activated):

```powershell
python -m uvicorn vking_proto.app:app --host 127.0.0.1 --port 9000
```

Open [http://127.0.0.1:9000](http://127.0.0.1:9000).

Or use the Makefile (from repo root, adjust `PYTHON` if needed):

```bash
make -C prototype run
```

## Makefile targets

| Target   | Action                                      |
|----------|---------------------------------------------|
| `run`    | Start uvicorn on port 9000                  |
| `doctor` | Print toolchain probe JSON                  |
| `clean`  | Remove `runs/` artifacts and `__pycache__` |

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Single-page UI |
| GET | `/api/doctor` | Toolchain status (`iverilog`, `vvp`, `gtkwave`) |
| GET | `/api/demo/counter` | Demo Verilog source |
| POST | `/api/parse` | Parse source → ports |
| POST | `/api/run` | Parse + TB gen + sim → manifest, logs, artifacts |
| GET | `/api/artifacts/{run_id}/{filename}` | Download run artifacts |
| POST | `/api/delta` | VCD-based delta reconstruction at `time_ns` |
| POST | `/api/gtkwave` | Launch GTKWave (detached on Windows) |

## Typical flow

1. Click **Load Demo** (8-bit counter).
2. **Parse ports** or **Run simulation** directly.
3. Review **G1 / G1.5 / G2** chips (each labeled with backend).
4. Download TB / Makefile / waves, or **Open waves in GTKWave**.
5. Optionally probe **Reconstructed delta** at a chosen time (VCD only).

Simulation artifacts are written under `prototype/runs/<run_id>/`.
