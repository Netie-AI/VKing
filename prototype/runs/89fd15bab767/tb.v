`timescale 1ns/1ps

module tb_top;

  localparam integer RESET_CYCLES = 5;
  localparam integer XCHECK_DELAY = 10;
  localparam integer WATCHDOG_CYCLES = 1000;
  localparam integer VACUITY_MIN = 1;

  reg clk;
  reg rst_n;
  reg en;
  wire [WIDTH-1:0] count;

  integer cycle_count;
  integer settle_cycle;
  reg reset_released;
  integer vac_reset_release;
  integer vac_xcheck;
  integer vac_clk_edges;

  counter u_dut (
    .clk(clk),
    .rst_n(rst_n),
    .en(en),
    .count(count)
  );

  initial clk = 1'b0;
  always #5 clk = ~clk;

  initial begin
    $dumpfile("waves.fst");
    $dumpvars(0, tb_top);
  end

  initial begin
    cycle_count = 0;
    settle_cycle = -1;
    reset_released = 1'b0;
    vac_reset_release = 0;
    vac_xcheck = 0;
    vac_clk_edges = 0;
    rst_n = 1'b0;
    en = 1'b0;
    repeat (RESET_CYCLES) @(negedge clk);
    rst_n = 1'b1;
    reset_released = 1'b1;
    vac_reset_release = vac_reset_release + 1;
    settle_cycle = cycle_count + XCHECK_DELAY;
  end

  // style law: drive DUT inputs on negedge clk
  always @(negedge clk) begin
      en <= ~en;
  end

  // style law: sample/check on posedge clk
  always @(posedge clk) begin
    cycle_count = cycle_count + 1;
    if (reset_released) begin
      vac_clk_edges = vac_clk_edges + 1;
    end
    if (cycle_count > WATCHDOG_CYCLES) begin
      $display("VKING_RESULT: TIMEOUT watchdog at cycle %0d", cycle_count);
      $finish;
    end
    if (reset_released && cycle_count >= settle_cycle) begin
      vac_xcheck = vac_xcheck + 1;
        if (count === 1'bx || count === 1'bz) begin
          $display("VKING_RESULT: FAIL X on count at cycle %0d", cycle_count);
          $finish;
        end
    end
  end

  initial begin
    wait (cycle_count >= (RESET_CYCLES + XCHECK_DELAY + 20));
    $display("VKING_VACUITY: reset_release %0d", vac_reset_release);
    $display("VKING_VACUITY: xcheck %0d", vac_xcheck);
    $display("VKING_VACUITY: clk_edges %0d", vac_clk_edges);
    if (vac_reset_release < VACUITY_MIN) begin
      $display("VKING_RESULT: VACUOUS reset_release");
      $finish;
    end
    if (vac_xcheck < VACUITY_MIN) begin
      $display("VKING_RESULT: VACUOUS xcheck");
      $finish;
    end
    if (vac_clk_edges < VACUITY_MIN) begin
      $display("VKING_RESULT: VACUOUS clk_edges");
      $finish;
    end
    $display("VKING_RESULT: PASS");
    $finish;
  end

endmodule
