`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module regfile (
    input logic i_clk,
    input logic i_rst_n,
    input logic i_we,
    input logic [4:0] i_rs1,
    input logic [4:0] i_rs2,
    input logic [4:0] i_rd,
    input logic [31:0] i_wdata,
    output logic [31:0] o_rdata1,
    output logic [31:0] o_rdata2
);

    // SystemVerilog section: section_sv_regfile
`line 1 "annotations/entity-sections/sv/section_sv_regfile.sv" 0
logic [31:0] regs [0:31];
    always_ff @(posedge i_clk or negedge i_rst_n) begin
        if (!i_rst_n) begin
            for (int n = 0; n < 32; n++) regs[n] <= '0;
        end else if (i_we && (i_rd != '0) && (int'(i_rd) < 32))
            regs[i_rd] <= i_wdata;
    end
    // No WB-to-ID bypass: a dependent ID must occur after the WB clock edge.
    always_comb begin
        o_rdata1 = '0;
        o_rdata2 = '0;
        if ((i_rs1 != '0) && (int'(i_rs1) < 32)) o_rdata1 = regs[i_rs1];
        if ((i_rs2 != '0) && (int'(i_rs2) < 32)) o_rdata2 = regs[i_rs2];
    end
`line 1 "rtl/components/regfile.sv" 0
endmodule

`default_nettype wire
