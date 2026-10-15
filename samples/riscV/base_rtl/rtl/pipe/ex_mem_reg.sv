`include "riscv_defs.svh"
module ex_mem_reg (
    input logic i_clk, i_rst_n, i_flush,
    input ex_mem_t i_d,
    output ex_mem_t o_q
);
    pipe_reg #(.T(ex_mem_t)) u_reg (.i_clk, .i_rst_n, .i_flush, .i_d, .o_q);
endmodule
