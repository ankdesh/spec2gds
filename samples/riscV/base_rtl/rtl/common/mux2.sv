`include "riscv_defs.svh"
module mux2 #(parameter int WIDTH = 32) (
    input logic [WIDTH-1:0] i_a, i_b,
    input logic i_sel,
    output logic [WIDTH-1:0] o_y
);
    assign o_y = i_sel ? i_b : i_a;
endmodule
