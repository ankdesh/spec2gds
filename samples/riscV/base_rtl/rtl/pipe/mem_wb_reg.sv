`include "riscv_defs.svh"
module mem_wb_reg (
    input logic i_clk, i_rst_n, i_flush,
    input mem_wb_t i_d,
    output mem_wb_t o_q
);
    pipe_reg #(.T(mem_wb_t)) u_reg (.i_clk, .i_rst_n, .i_flush, .i_d, .o_q);
endmodule
