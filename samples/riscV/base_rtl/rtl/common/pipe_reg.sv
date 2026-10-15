`include "riscv_defs.svh"
module pipe_reg #(parameter type T = logic [31:0]) (
    input logic i_clk, i_rst_n, i_flush,
    input T i_d,
    output T o_q
);
    always_ff @(posedge i_clk or negedge i_rst_n)
        if (!i_rst_n) o_q <= '0;
        else if (i_flush) o_q <= '0;
        else o_q <= i_d;
endmodule
