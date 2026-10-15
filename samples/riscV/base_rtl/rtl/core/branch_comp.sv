`include "riscv_defs.svh"
module branch_comp #(parameter int WIDTH = 32) (
    input logic [WIDTH-1:0] i_a, i_b,
    input logic i_ne,
    output logic o_taken
);
    assign o_taken = i_ne ? (i_a != i_b) : (i_a == i_b);
endmodule
