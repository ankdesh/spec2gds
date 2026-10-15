`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module control (
    input logic [31:0] i_inst,
    output logic [14:0] o_ctrl,
    output logic o_legal
);

    // SystemVerilog section: section_sv_control
`line 1 "annotations/entity-sections/sv/section_sv_control.sv" 0
typedef enum logic {ALU_ADD, ALU_MUL} alu_op_t;
typedef enum logic [2:0] {IMM_I, IMM_S, IMM_B, IMM_U, IMM_J} imm_sel_t;
typedef enum logic [1:0] {WB_ALU, WB_MEM, WB_PC4} wb_sel_t;
typedef struct packed {
    imm_sel_t imm_sel;
    logic a_pc;
    logic a_zero;
    logic b_imm;
    alu_op_t alu_op;
    logic mem_write;
    logic mem_read;
    wb_sel_t wb_sel;
    logic reg_write;
    logic branch;
    logic branch_ne;
    logic jump;
} ctrl_t;
ctrl_t decoded;
assign o_ctrl = decoded;
always_comb begin
        decoded = '0;
        decoded.imm_sel = IMM_I;
        decoded.alu_op = ALU_ADD;
        decoded.wb_sel = WB_ALU;
        o_legal = 1'b0;
        case (i_inst[6:0])
            7'b0110011: begin // ADD / MUL only; reject other funct7 values.
                if ((i_inst[14:12] == 3'b000) &&
                    ((i_inst[31:25] == 7'b0000000) || (i_inst[31:25] == 7'b0000001))) begin
                    o_legal = 1'b1;
                    decoded.reg_write = 1'b1;
                    decoded.alu_op = i_inst[25] ? ALU_MUL : ALU_ADD;
                end
            end
            7'b0010011: begin // ADDI
                if (i_inst[14:12] == 3'b000) begin
                    o_legal = 1'b1;
                    decoded.reg_write = 1'b1;
                    decoded.b_imm = 1'b1;
                end
            end
            7'b0000011: begin // LW
                if (i_inst[14:12] == 3'b010) begin
                    o_legal = 1'b1;
                    decoded.b_imm = 1'b1;
                    decoded.mem_read = 1'b1;
                    decoded.wb_sel = WB_MEM;
                    decoded.reg_write = 1'b1;
                end
            end
            7'b0100011: begin // SW
                if (i_inst[14:12] == 3'b010) begin
                    o_legal = 1'b1;
                    decoded.imm_sel = IMM_S;
                    decoded.b_imm = 1'b1;
                    decoded.mem_write = 1'b1;
                end
            end
            7'b1100011: begin // BEQ / BNE, compared outside the ALU.
                if ((i_inst[14:12] == 3'b000) || (i_inst[14:12] == 3'b001)) begin
                    o_legal = 1'b1;
                    decoded.imm_sel = IMM_B;
                    decoded.a_pc = 1'b1;
                    decoded.b_imm = 1'b1;
                    decoded.branch = 1'b1;
                    decoded.branch_ne = i_inst[12];
                end
            end
            7'b1101111: begin // JAL
                o_legal = 1'b1;
                decoded.imm_sel = IMM_J;
                decoded.a_pc = 1'b1;
                decoded.b_imm = 1'b1;
                decoded.wb_sel = WB_PC4;
                decoded.reg_write = 1'b1;
                decoded.jump = 1'b1;
            end
            7'b0110111: begin // LUI: rs1 bits are part of the immediate.
                o_legal = 1'b1;
                decoded.imm_sel = IMM_U;
                decoded.a_zero = 1'b1;
                decoded.b_imm = 1'b1;
                decoded.reg_write = 1'b1;
            end
            default: begin end // Unsupported encodings become inert bubbles.
        endcase
    end
`line 1 "rtl/components/control.sv" 0
endmodule

`default_nettype wire
