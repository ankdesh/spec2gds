`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module two_bit_mux (
    input logic [1:0] a,
    input logic [1:0] b,
    input logic [0:0] sel,
    output logic [1:0] f
);

    // SystemVerilog section: section_sv_component_two_bit_mux_3441eea48c9e430eba8f3b100f568f08
`line 1 "annotations/entity-sections/sv/section_sv_component_two_bit_mux_3441eea48c9e430eba8f3b100f568f08.sv" 0
mux mux_1(.f(f[0]), .a(a[0]), .b(b[0]), .sel);
mux mux_2(.f(f[1]), .a(a[1]), .b(b[1]), .sel);
`line 1 "rtl/components/two_bit_mux.sv" 0
endmodule

`default_nettype wire
