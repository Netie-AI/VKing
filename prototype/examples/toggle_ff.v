`timescale 1ns/1ps

// Toggles q every cycle when en is high (good wave sanity check).
module toggle_ff (
  input  wire clk,
  input  wire rst_n,
  input  wire en,
  output reg  q
);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      q <= 1'b0;
    else if (en)
      q <= ~q;
  end

endmodule
