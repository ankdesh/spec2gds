`include "riscv_defs.svh"
module regfile #(
    parameter int WIDTH = XLEN,
    parameter int ADDR_W = REG_ADDR,
    parameter int DEPTH = NREG
) (
    input logic i_clk, i_rst_n, i_we,
    input logic [ADDR_W-1:0] i_rs1, i_rs2, i_rd,
    input logic [WIDTH-1:0] i_wdata,
    output logic [WIDTH-1:0] o_rdata1, o_rdata2
);
    logic [WIDTH-1:0] regs [0:DEPTH-1];
    always_ff @(posedge i_clk or negedge i_rst_n) begin
        if (!i_rst_n) begin
            for (int n = 0; n < DEPTH; n++) regs[n] <= '0;
        end else if (i_we && (i_rd != '0) && (int'(i_rd) < DEPTH))
            regs[i_rd] <= i_wdata;
    end
    // No WB-to-ID bypass: a dependent ID must occur after the WB clock edge.
    always_comb begin
        o_rdata1 = '0;
        o_rdata2 = '0;
        if ((i_rs1 != '0) && (int'(i_rs1) < DEPTH)) o_rdata1 = regs[i_rs1];
        if ((i_rs2 != '0) && (int'(i_rs2) < DEPTH)) o_rdata2 = regs[i_rs2];
    end
endmodule
