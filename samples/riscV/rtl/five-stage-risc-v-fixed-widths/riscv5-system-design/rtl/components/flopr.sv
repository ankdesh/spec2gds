`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module flopr (
    input logic i_clk,
    input logic i_rst_n,
    input logic [31:0] i_d,
    output logic [31:0] o_q
);

    // SystemVerilog section: section_sv_flopr
`line 1 "annotations/entity-sections/sv/section_sv_flopr.sv" 0
always_ff @(posedge i_clk or negedge i_rst_n)
        if (!i_rst_n) o_q <= 32'b0;
        else o_q <= i_d;
`line 1 "rtl/components/flopr.sv" 0
endmodule

`default_nettype wire
