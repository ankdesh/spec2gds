`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module branch_comp (
    input logic [31:0] i_a,
    input logic [31:0] i_b,
    input logic i_ne,
    output logic o_taken
);

    // SystemVerilog section: section_sv_branch_comp
`line 1 "annotations/entity-sections/sv/section_sv_branch_comp.sv" 0
assign o_taken = i_ne ? (i_a != i_b) : (i_a == i_b);
`line 1 "rtl/components/branch_comp.sv" 0
endmodule

`default_nettype wire
