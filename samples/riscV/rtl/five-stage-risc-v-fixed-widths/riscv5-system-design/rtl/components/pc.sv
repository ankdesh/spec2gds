`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module pc (
    input logic i_clk,
    input logic i_rst_n,
    input logic [31:0] i_next,
    output logic [31:0] o_pc
);

    // SystemVerilog section: section_sv_pc
`line 1 "annotations/entity-sections/sv/section_sv_pc.sv" 0
flopr  u_pc (
        .i_clk, .i_rst_n, .i_d(i_next), .o_q(o_pc)
    );
`line 1 "rtl/components/pc.sv" 0
endmodule

`default_nettype wire
