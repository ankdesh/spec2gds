`include "riscv_defs.svh"
module pc #(
    parameter int WIDTH = 32,
    parameter logic [WIDTH-1:0] RESET_PC = '0
) (
    input logic i_clk, i_rst_n,
    input logic [WIDTH-1:0] i_next,
    output logic [WIDTH-1:0] o_pc
);
    flopr #(.WIDTH(WIDTH), .RESET_VALUE(RESET_PC)) u_pc (
        .i_clk, .i_rst_n, .i_d(i_next), .o_q(o_pc)
    );
endmodule
