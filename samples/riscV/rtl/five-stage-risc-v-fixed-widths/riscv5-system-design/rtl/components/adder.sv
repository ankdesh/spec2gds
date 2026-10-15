`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module adder (
    input logic [31:0] i_a,
    input logic [31:0] i_b,
    output logic [31:0] o_sum
);

    // SystemVerilog section: section_sv_adder
`line 1 "annotations/entity-sections/sv/section_sv_adder.sv" 0
assign o_sum = i_a + i_b;
`line 1 "rtl/components/adder.sv" 0
endmodule

`default_nettype wire
