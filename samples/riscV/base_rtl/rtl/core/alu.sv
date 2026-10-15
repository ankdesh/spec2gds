`include "riscv_defs.svh"
module alu #(parameter int WIDTH = 32) (
    input logic [WIDTH-1:0] i_a, i_b,
    input alu_op_t i_op,
    output logic [WIDTH-1:0] o_result
);
    logic [WIDTH-1:0] sum, product;
    adder #(.WIDTH(WIDTH)) u_add (.i_a, .i_b, .o_sum(sum));
    multiplier #(.WIDTH(WIDTH)) u_mul (.i_a, .i_b, .o_product(product));
    mux2 #(.WIDTH(WIDTH)) u_result (
        .i_a(sum), .i_b(product), .i_sel(i_op == ALU_MUL), .o_y(o_result)
    );
endmodule
