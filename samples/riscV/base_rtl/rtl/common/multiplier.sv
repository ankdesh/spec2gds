`include "riscv_defs.svh"
module multiplier #(parameter int WIDTH = 32) (
    input logic [WIDTH-1:0] i_a, i_b,
    output logic [WIDTH-1:0] o_product
);
    // Truncation implements the low WIDTH bits of a two's-complement product.
    assign o_product = $signed(i_a) * $signed(i_b);
endmodule
