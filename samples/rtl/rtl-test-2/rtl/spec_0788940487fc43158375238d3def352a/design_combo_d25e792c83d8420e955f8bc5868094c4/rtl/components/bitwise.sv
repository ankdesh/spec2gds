`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module bitwise (
    input logic [0:0] a,
    input logic [0:0] b,
    input logic [4:0] c,
    input logic [4:0] d,
    output logic [0:0] res
);

    // SystemVerilog section: section_sv_component_bitwise_674c75e21cc7439d95402d4ebc5cac39
`line 1 "annotations/entity-sections/sv/section_sv_component_bitwise_674c75e21cc7439d95402d4ebc5cac39.sv" 0
logic e, f, g;
assign e = a | b;
assign f = ^a & b;
assign g = e ^ f;

logic [4:0] h;
assign h = c + d;
assign res = &h | g;
`line 1 "rtl/components/bitwise.sv" 0
endmodule

`default_nettype wire
