`include "riscv_defs.svh"
module control (
    input logic [31:0] i_inst,
    output ctrl_t o_ctrl,
    output logic o_legal
);
    always_comb begin
        o_ctrl = '0;
        o_ctrl.imm_sel = IMM_I;
        o_ctrl.alu_op = ALU_ADD;
        o_ctrl.wb_sel = WB_ALU;
        o_legal = 1'b0;
        case (i_inst[6:0])
            7'b0110011: begin // ADD / MUL only; reject other funct7 values.
                if ((i_inst[14:12] == 3'b000) &&
                    ((i_inst[31:25] == 7'b0000000) || (i_inst[31:25] == 7'b0000001))) begin
                    o_legal = 1'b1;
                    o_ctrl.reg_write = 1'b1;
                    o_ctrl.alu_op = i_inst[25] ? ALU_MUL : ALU_ADD;
                end
            end
            7'b0010011: begin // ADDI
                if (i_inst[14:12] == 3'b000) begin
                    o_legal = 1'b1;
                    o_ctrl.reg_write = 1'b1;
                    o_ctrl.b_imm = 1'b1;
                end
            end
            7'b0000011: begin // LW
                if (i_inst[14:12] == 3'b010) begin
                    o_legal = 1'b1;
                    o_ctrl.b_imm = 1'b1;
                    o_ctrl.mem_read = 1'b1;
                    o_ctrl.wb_sel = WB_MEM;
                    o_ctrl.reg_write = 1'b1;
                end
            end
            7'b0100011: begin // SW
                if (i_inst[14:12] == 3'b010) begin
                    o_legal = 1'b1;
                    o_ctrl.imm_sel = IMM_S;
                    o_ctrl.b_imm = 1'b1;
                    o_ctrl.mem_write = 1'b1;
                end
            end
            7'b1100011: begin // BEQ / BNE, compared outside the ALU.
                if ((i_inst[14:12] == 3'b000) || (i_inst[14:12] == 3'b001)) begin
                    o_legal = 1'b1;
                    o_ctrl.imm_sel = IMM_B;
                    o_ctrl.a_pc = 1'b1;
                    o_ctrl.b_imm = 1'b1;
                    o_ctrl.branch = 1'b1;
                    o_ctrl.branch_ne = i_inst[12];
                end
            end
            7'b1101111: begin // JAL
                o_legal = 1'b1;
                o_ctrl.imm_sel = IMM_J;
                o_ctrl.a_pc = 1'b1;
                o_ctrl.b_imm = 1'b1;
                o_ctrl.wb_sel = WB_PC4;
                o_ctrl.reg_write = 1'b1;
                o_ctrl.jump = 1'b1;
            end
            7'b0110111: begin // LUI: rs1 bits are part of the immediate.
                o_legal = 1'b1;
                o_ctrl.imm_sel = IMM_U;
                o_ctrl.a_zero = 1'b1;
                o_ctrl.b_imm = 1'b1;
                o_ctrl.reg_write = 1'b1;
            end
            default: begin end // Unsupported encodings become inert bubbles.
        endcase
    end
endmodule
