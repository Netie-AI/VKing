"""Deterministic clk_rst_smoke testbench generator (§6.1 style law)."""

from __future__ import annotations

from dataclasses import dataclass

from .ingest import ModuleView, Port


@dataclass
class TbGenConfig:
    reset_cycles: int = 5
    xcheck_delay: int = 10
    watchdog_cycles: int = 1000
    vacuity_min: int = 1
    timescale: str = "1ns/1ps"
    wave_filename: str = "waves.vcd"
    tb_top: str = "tb_top"
    clock_period: str = "5"


_CLK_NAMES = frozenset({"clk", "clock", "iclk", "sclk", "pclk", "aclk", "hclk"})
_RST_NAMES = frozenset(
    {
        "rst",
        "reset",
        "rst_n",
        "resetn",
        "rstn",
        "areset",
        "aresetn",
        "srst",
        "srst_n",
    }
)


def _is_clk(port: Port) -> bool:
    return port.name.lower() in _CLK_NAMES or port.name.lower().endswith("_clk")


def _is_rst(port: Port) -> bool:
    lowered = port.name.lower()
    if lowered in _RST_NAMES:
        return True
    return lowered.startswith("rst") or lowered.startswith("reset")


def _verilog_type(port: Port, *, for_tb_drive: bool) -> str:
    base = "reg" if for_tb_drive and port.direction == "input" else "wire"
    if port.width_expr:
        return f"{base} {port.width_expr}"
    return base


def _port_decl(port: Port, *, for_tb_drive: bool) -> str:
    return f"  {_verilog_type(port, for_tb_drive=for_tb_drive)} {port.name};"


def _instance_conn(port: Port) -> str:
    return f".{port.name}({port.name})"


def generate_clk_rst_smoke(view: ModuleView, config: TbGenConfig | None = None) -> str:
    """Generate Profile A (V2005-safe) clk_rst_smoke testbench for *view*."""
    cfg = config or TbGenConfig()
    if view.timescale:
        cfg.timescale = view.timescale

    clk_ports = [p for p in view.ports if _is_clk(p)]
    rst_ports = [p for p in view.ports if _is_rst(p)]
    if not clk_ports:
        raise ValueError(f"No clock port detected for module {view.name}")
    clk = clk_ports[0]

    inputs = [p for p in view.ports if p.direction == "input" and p is not clk and p not in rst_ports]
    outputs = [p for p in view.ports if p.direction in ("output", "inout")]

    rst_assert: list[str] = []
    rst_release: list[str] = []
    for rp in rst_ports:
        active_low = rp.name.lower().endswith("_n") or rp.name.lower().endswith("n")
        if active_low:
            rst_assert.append(f"    {rp.name} = 1'b0;")
            rst_release.append(f"    {rp.name} = 1'b1;")
        else:
            rst_assert.append(f"    {rp.name} = 1'b1;")
            rst_release.append(f"    {rp.name} = 1'b0;")

    input_init: list[str] = [f"    {inp.name} = 1'b0;" for inp in inputs]
    negedge_drive: list[str] = []
    if inputs:
        negedge_drive.append(f"      {inputs[0].name} <= ~{inputs[0].name};")

    x_checks: list[str] = []
    for out in outputs:
        if _is_clk(out) or _is_rst(out):
            continue
        if out.width_expr:
            x_checks.append(
                f"        if ((^({out.name})) === 1'bx || (^({out.name})) === 1'bz) begin\n"
                f"          $display(\"VKING_RESULT: FAIL X on {out.name} at cycle %0d\", cycle_count);\n"
                f"          $finish;\n"
                f"        end"
            )
        else:
            x_checks.append(
                f"        if ({out.name} === 1'bx || {out.name} === 1'bz) begin\n"
                f"          $display(\"VKING_RESULT: FAIL X on {out.name} at cycle %0d\", cycle_count);\n"
                f"          $finish;\n"
                f"        end"
            )

    decls = [_port_decl(p, for_tb_drive=True) for p in view.ports]
    inst_conns = ",\n    ".join(_instance_conn(p) for p in view.ports)

    param_lines: list[str] = []
    for pname, pdefault in view.param_defaults.items():
        param_lines.append(f"  localparam {pname} = {pdefault};")
    if param_lines:
        param_lines.append("")

    lines = [
        f"`timescale {cfg.timescale}",
        "",
        f"module {cfg.tb_top};",
        "",
        f"  localparam integer RESET_CYCLES = {cfg.reset_cycles};",
        f"  localparam integer XCHECK_DELAY = {cfg.xcheck_delay};",
        f"  localparam integer WATCHDOG_CYCLES = {cfg.watchdog_cycles};",
        f"  localparam integer VACUITY_MIN = {cfg.vacuity_min};",
        "",
        *param_lines,
        *decls,
        "",
        "  integer cycle_count;",
        "  integer settle_cycle;",
        "  reg reset_released;",
        "  integer vac_reset_release;",
        "  integer vac_xcheck;",
        "  integer vac_clk_edges;",
        "",
        f"  {view.name} u_dut (",
        f"    {inst_conns}",
        "  );",
        "",
        f"  initial {clk.name} = 1'b0;",
        f"  always #{cfg.clock_period} {clk.name} = ~{clk.name};",
        "",
        "  // VCD: GTKWave + reconstructed delta panel (single artifact, no -fst pass)",
        "  initial begin",
        f'    $dumpfile("{cfg.wave_filename}");',
        f"    $dumpvars(0, {cfg.tb_top});",
        "  end",
        "",
        "  initial begin",
        "    cycle_count = 0;",
        "    settle_cycle = -1;",
        "    reset_released = 1'b0;",
        "    vac_reset_release = 0;",
        "    vac_xcheck = 0;",
        "    vac_clk_edges = 0;",
        *rst_assert,
        *input_init,
        f"    repeat (RESET_CYCLES) @(negedge {clk.name});",
        *rst_release,
        "    reset_released = 1'b1;",
        "    vac_reset_release = vac_reset_release + 1;",
        "    settle_cycle = cycle_count + XCHECK_DELAY;",
        "  end",
        "",
    ]

    if negedge_drive:
        lines.extend(
            [
                f"  // style law: drive DUT inputs on negedge {clk.name}",
                f"  always @(negedge {clk.name}) begin",
                *negedge_drive,
                "  end",
                "",
            ]
        )

    lines.extend(
        [
            f"  // style law: sample/check on posedge {clk.name}",
            f"  always @(posedge {clk.name}) begin",
            "    cycle_count = cycle_count + 1;",
            "    if (reset_released) begin",
            "      vac_clk_edges = vac_clk_edges + 1;",
            "    end",
            "    if (cycle_count > WATCHDOG_CYCLES) begin",
            '      $display("VKING_RESULT: TIMEOUT watchdog at cycle %0d", cycle_count);',
            "      $finish;",
            "    end",
            "    if (reset_released && cycle_count >= settle_cycle) begin",
            "      vac_xcheck = vac_xcheck + 1;",
            *x_checks,
            "    end",
            "  end",
            "",
            "  initial begin",
            f"    wait (cycle_count >= (RESET_CYCLES + XCHECK_DELAY + 20));",
            '    $display("VKING_VACUITY: reset_release %0d", vac_reset_release);',
            '    $display("VKING_VACUITY: xcheck %0d", vac_xcheck);',
            '    $display("VKING_VACUITY: clk_edges %0d", vac_clk_edges);',
            "    if (vac_reset_release < VACUITY_MIN) begin",
            '      $display("VKING_RESULT: VACUOUS reset_release");',
            "      $finish;",
            "    end",
            "    if (vac_xcheck < VACUITY_MIN) begin",
            '      $display("VKING_RESULT: VACUOUS xcheck");',
            "      $finish;",
            "    end",
            "    if (vac_clk_edges < VACUITY_MIN) begin",
            '      $display("VKING_RESULT: VACUOUS clk_edges");',
            "      $finish;",
            "    end",
            '    $display("VKING_RESULT: PASS");',
            "    $finish;",
            "  end",
            "",
            "endmodule",
            "",
        ]
    )

    return "\n".join(lines)


def generate(
    module_name: str,
    ports: list[dict[str, str]],
    parameters: list[dict[str, str]] | None = None,
    timescale: str = "1ns/1ps",
) -> dict[str, str]:
    """Dict-shaped TB bundle for the FastAPI prototype UI."""
    _ = parameters
    view_ports = []
    for item in ports:
        width_expr = None
        if item.get("width") and item["width"] != "0":
            width_expr = f"[{item['width']}]"
        view_ports.append(
            Port(name=item["name"], direction=item["direction"], width_expr=width_expr)
        )
    view = ModuleView(name=module_name, ports=view_ports, timescale=timescale)
    cfg = TbGenConfig(timescale=timescale)
    tb = generate_clk_rst_smoke(view, cfg)
    makefile = f"""# Generated by Vking prototype — clk_rst_smoke
IVERILOG ?= iverilog
VVP ?= vvp
TOP ?= {cfg.tb_top}
WAVE ?= {cfg.wave_filename}

all: sim

sim: run.vvp
\t$(VVP) -n -l run.log run.vvp

run.vvp: dut.v tb.v
\t$(IVERILOG) -g2012 -o $@ -s $(TOP) dut.v tb.v

waves:
\tgtkwave $(WAVE)

clean:
\trm -f run.vvp run.log $(WAVE)
"""
    return {
        "tb": tb,
        "makefile": makefile,
        "filelist": "dut.v\ntb.v\n",
        "template": "clk_rst_smoke",
        "wave_filename": cfg.wave_filename,
        "timescale": timescale,
    }
