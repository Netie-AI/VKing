`timescale 1ns/1ps

// 4-bit shift register — watch q_out bus change in Waves tab.
module shift4 (
  input  wire       clk,
  input  wire       rst_n,
  input  wire       shift_en,
  input  wire       d_in,
  output reg  [3:0] q_out
);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n)
      q_out <= 4'b0;
    else if (shift_en)
      q_out <= {q_out[2:0], d_in};
  end

endmodule
