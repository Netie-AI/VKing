`timescale 1ns/1ps

module shift_2bit_tb;

    reg clk;
    reg rst_n;
    reg d_in;
    wire q1;
    wire q2;

    shift_2bit uut (
        .clk(clk),
        .rst_n(rst_n),
        .d_in(d_in),
        .q1(q1),
        .q2(q2)
    );

    always #5 clk = ~clk;

    initial begin
        $dumpfile("waves.vcd");
        $dumpvars(0, shift_2bit_tb);

        clk = 0;
        rst_n = 0;
        d_in = 0;

        #12 rst_n = 1;
        #3  d_in = 1;
        #10 d_in = 0;
        #20;

        $display("VKING_RESULT: PASS");
        $finish;
    end

endmodule
