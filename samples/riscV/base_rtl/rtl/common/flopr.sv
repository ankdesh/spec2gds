`include "riscv_defs.svh"
module flopr #(
    parameter int WIDTH = 32,
    parameter logic [WIDTH-1:0] RESET_VALUE = '0
) (
    input logic i_clk, i_rst_n,
    input logic [WIDTH-1:0] i_d,
    output logic [WIDTH-1:0] o_q
);
    always_ff @(posedge i_clk or negedge i_rst_n)
        if (!i_rst_n) o_q <= RESET_VALUE;
        else o_q <= i_d;
endmodule
