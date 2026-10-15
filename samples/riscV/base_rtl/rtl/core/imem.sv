`include "riscv_defs.svh"
module imem #(
    parameter int DEPTH = 256,
    parameter int ADDR_W = 32,
    parameter int WIDTH = 32,
    parameter string FILE = ""
) (
    input logic [ADDR_W-1:0] i_addr,
    output logic [WIDTH-1:0] o_inst
);
    localparam int BYTE_BITS = $clog2(WIDTH / 8);
    logic [WIDTH-1:0] mem [0:DEPTH-1];
    // Initialized ROM; a synthesis flow must support memory initialization.
    initial begin
        for (int n = 0; n < DEPTH; n++) mem[n] = WIDTH'(32'h00000013);
        if (FILE != "") $readmemh(FILE, mem);
    end
    always_comb begin
        o_inst = WIDTH'(32'h00000013);
        if ((i_addr[BYTE_BITS-1:0] == '0) && ((i_addr >> BYTE_BITS) < DEPTH))
            o_inst = mem[i_addr >> BYTE_BITS];
    end
endmodule
