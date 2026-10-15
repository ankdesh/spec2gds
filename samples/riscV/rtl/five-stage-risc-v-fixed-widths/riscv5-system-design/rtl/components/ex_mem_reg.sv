`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module ex_mem_reg (
    input logic i_clk,
    input logic i_rst_n,
    input logic i_flush,
    input logic [149:0] i_d,
    output logic [149:0] o_q
);

    // SystemVerilog section: section_sv_ex_mem_reg
`line 1 "annotations/entity-sections/sv/section_sv_ex_mem_reg.sv" 0
always_ff @(posedge i_clk or negedge i_rst_n)
    if (!i_rst_n) o_q <= '0;
    else if (i_flush) o_q <= '0;
    else o_q <= i_d;
`line 1 "rtl/components/ex_mem_reg.sv" 0
endmodule

`default_nettype wire
