`include "riscv_defs.svh"
module dmem #(
    parameter int DEPTH = 256,
    parameter int ADDR_W = 32,
    parameter int WIDTH = 32
) (
    input logic i_clk, i_rst_n, i_read, i_write,
    input logic [ADDR_W-1:0] i_addr,
    input logic [WIDTH-1:0] i_wdata,
    output logic [WIDTH-1:0] o_rdata
);
    localparam int BYTE_BITS = $clog2(WIDTH / 8);
    logic [WIDTH-1:0] mem [0:DEPTH-1];
    logic address_valid;
    assign address_valid = (i_addr[BYTE_BITS-1:0] == '0) &&
                           ((i_addr >> BYTE_BITS) < DEPTH);
    always_ff @(posedge i_clk or negedge i_rst_n) begin
        if (!i_rst_n) begin
            for (int n = 0; n < DEPTH; n++) mem[n] <= '0;
        end else if (i_write && address_valid)
            mem[i_addr >> BYTE_BITS] <= i_wdata;
    end
    always_comb begin
        o_rdata = '0;
        if (i_rst_n && i_read && address_valid) o_rdata = mem[i_addr >> BYTE_BITS];
    end
endmodule
