`include "riscv_defs.svh"
module if_id_reg (
    input logic i_clk, i_rst_n, i_flush,
    input if_id_t i_d,
    output if_id_t o_q
);
    pipe_reg #(.T(if_id_t)) u_reg (.i_clk, .i_rst_n, .i_flush, .i_d, .o_q);
endmodule
