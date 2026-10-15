`include "riscv_defs.svh"
module imm_gen #(parameter int WIDTH = 32) (
    input logic [31:0] i_inst,
    input imm_sel_t i_sel,
    output logic [WIDTH-1:0] o_imm
);
    logic signed [31:0] imm;
    always_comb begin
        case (i_sel)
            IMM_I: imm = {{20{i_inst[31]}}, i_inst[31:20]};
            IMM_S: imm = {{20{i_inst[31]}}, i_inst[31:25], i_inst[11:7]};
            IMM_B: imm = {{19{i_inst[31]}}, i_inst[31], i_inst[7],
                          i_inst[30:25], i_inst[11:8], 1'b0};
            IMM_U: imm = {i_inst[31:12], 12'b0};
            IMM_J: imm = {{11{i_inst[31]}}, i_inst[31], i_inst[19:12],
                          i_inst[20], i_inst[30:21], 1'b0};
            default: imm = '0;
        endcase
        o_imm = WIDTH'(imm);
    end
endmodule
