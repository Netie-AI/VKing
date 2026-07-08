`timescale 1ns/1ps

module shift_2bit (
    input wire clk,
    input wire rst_n,
    input wire d_in,
    output reg q1,
    output reg q2
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q1 <= 1'b0;
            q2 <= 1'b0;
        end else begin
            q1 <= d_in;
            q2 <= q1;
        end
    end

endmodule
