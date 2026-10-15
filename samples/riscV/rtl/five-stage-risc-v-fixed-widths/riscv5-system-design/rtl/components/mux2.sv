`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module mux2 (
    input logic [31:0] i_a,
    input logic [31:0] i_b,
    input logic i_sel,
    output logic [31:0] o_y
);

    // SystemVerilog section: section_sv_mux2
`line 1 "annotations/entity-sections/sv/section_sv_mux2.sv" 0
assign o_y = i_sel ? i_b : i_a;
`line 1 "rtl/components/mux2.sv" 0
endmodule

`default_nettype wire
