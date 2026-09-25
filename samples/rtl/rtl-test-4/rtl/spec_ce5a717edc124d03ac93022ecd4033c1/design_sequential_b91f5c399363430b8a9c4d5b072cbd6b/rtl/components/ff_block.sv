`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module ff_block (
    input logic [0:0] clk,
    input logic [0:0] d,
    output logic [0:0] q
);

    // SystemVerilog section: section_sv_component_ff_block_313d0340fd664491a4a480285e7c024c
`line 1 "annotations/entity-sections/sv/section_sv_component_ff_block_313d0340fd664491a4a480285e7c024c.sv" 0
always_ff @(posedge clk) begin
    q <= d;
end
`line 1 "rtl/components/ff_block.sv" 0
endmodule

`default_nettype wire
