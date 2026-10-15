`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module alu (
    input logic [31:0] i_a,
    input logic [31:0] i_b,
    input logic i_op,
    output logic [31:0] o_result
);

    // SystemVerilog section: section_sv_alu
`line 1 "annotations/entity-sections/sv/section_sv_alu.sv" 0
logic [31:0] sum, product;
    adder  u_add (.i_a, .i_b, .o_sum(sum));
    multiplier  u_mul (.i_a, .i_b, .o_product(product));
    mux2  u_result (
        .i_a(sum), .i_b(product), .i_sel(i_op == 1'b1), .o_y(o_result)
    );
`line 1 "rtl/components/alu.sv" 0
endmodule

`default_nettype wire
