`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module multiplier (
    input logic [31:0] i_a,
    input logic [31:0] i_b,
    output logic [31:0] o_product
);

    // SystemVerilog section: section_sv_multiplier
`line 1 "annotations/entity-sections/sv/section_sv_multiplier.sv" 0
// Truncation implements the low 32 bits of a two's-complement product.
    assign o_product = $signed(i_a) * $signed(i_b);
`line 1 "rtl/components/multiplier.sv" 0
endmodule

`default_nettype wire
