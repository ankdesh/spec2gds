`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module riscv5_system (
    input wire i_clk,
    input wire i_rst_n,
    output wire [31:0] o_pc,
    output wire o_retire_valid,
    output wire o_retire_we,
    output wire [31:0] o_retire_pc,
    output wire [31:0] o_retire_inst,
    output wire [31:0] o_retire_data,
    output wire [4:0] o_retire_rd,
    output wire o_redirect
);

    riscv5_top u_core (
        .i_clk(i_clk),
        .i_rst_n(i_rst_n),
        .o_pc(o_pc),
        .o_retire_valid(o_retire_valid),
        .o_retire_we(o_retire_we),
        .o_retire_pc(o_retire_pc),
        .o_retire_inst(o_retire_inst),
        .o_retire_data(o_retire_data),
        .o_retire_rd(o_retire_rd),
        .o_redirect(o_redirect)
    );
endmodule

`default_nettype wire
