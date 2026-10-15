`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module dmem (
    input logic i_clk,
    input logic i_rst_n,
    input logic i_read,
    input logic i_write,
    input logic [31:0] i_addr,
    input logic [31:0] i_wdata,
    output logic [31:0] o_rdata
);

    // SystemVerilog section: section_sv_dmem
`line 1 "annotations/entity-sections/sv/section_sv_dmem.sv" 0

    logic [31:0] mem [0:255];
    logic address_valid;
    assign address_valid = (i_addr[1:0] == '0) &&
                           ((i_addr >> 2) < 256);
    always_ff @(posedge i_clk or negedge i_rst_n) begin
        if (!i_rst_n) begin
            for (int n = 0; n < 256; n++) mem[n] <= '0;
        end else if (i_write && address_valid)
            mem[i_addr >> 2] <= i_wdata;
    end
    always_comb begin
        o_rdata = '0;
        if (i_rst_n && i_read && address_valid) o_rdata = mem[i_addr >> 2];
    end
`line 1 "rtl/components/dmem.sv" 0
endmodule

`default_nettype wire
