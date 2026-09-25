`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module c0 (
    input logic [0:0] a,
    input logic [0:0] b,
    input logic [0:0] sel,
    output logic [0:0] f
);

    // SystemVerilog section: section_sv_component_c0_30d0dc30717d43e7838f699fb5cfc6cb
`line 1 "annotations/entity-sections/sv/section_sv_component_c0_30d0dc30717d43e7838f699fb5cfc6cb.sv" 0
    logic n_sel, f1, f2; 

    and g1(f1, a, n_sel);
    and g2 (f2, b, sel) ;
    or g3(f, f1, f2 );
    not g4(n_sel, sel);
`line 1 "rtl/components/c0.sv" 0
endmodule

`default_nettype wire
