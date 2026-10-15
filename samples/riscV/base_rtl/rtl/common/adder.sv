`include "riscv_defs.svh"
module adder #(parameter int WIDTH = 32) (
    input logic [WIDTH-1:0] i_a, i_b,
    output logic [WIDTH-1:0] o_sum
);
    assign o_sum = i_a + i_b;
endmodule
