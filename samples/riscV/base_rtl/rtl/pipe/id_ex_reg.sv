`include "riscv_defs.svh"
module id_ex_reg (
    input logic i_clk, i_rst_n, i_flush,
    input id_ex_t i_d,
    output id_ex_t o_q
);
    pipe_reg #(.T(id_ex_t)) u_reg (.i_clk, .i_rst_n, .i_flush, .i_d, .o_q);
endmodule
