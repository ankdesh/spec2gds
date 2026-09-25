`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module combinational (
    input logic [3:0] x,
    input logic [3:0] y,
    input logic [0:0] add_sel,
    output logic [3:0] z
);

    // SystemVerilog section: section_sv_component_combinational_f32368080e184590b33cfa3816c41153
`line 1 "annotations/entity-sections/sv/section_sv_component_combinational_f32368080e184590b33cfa3816c41153.sv" 0
always_comb begin
    if (add)
        z = x + y;
    else
        z = x - y;
end
`line 1 "rtl/components/combinational.sv" 0
endmodule

`default_nettype wire
