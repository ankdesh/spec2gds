`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module riscv5_top (
    input logic i_clk,
    input logic i_rst_n,
    output logic [31:0] o_pc,
    output logic o_retire_valid,
    output logic o_retire_we,
    output logic [31:0] o_retire_pc,
    output logic [31:0] o_retire_inst,
    output logic [31:0] o_retire_data,
    output logic [4:0] o_retire_rd,
    output logic o_redirect
);

    // SystemVerilog section: section_sv_riscv5_top
`line 1 "annotations/entity-sections/sv/section_sv_riscv5_top.sv" 0
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

typedef struct packed {
    logic valid;
    logic [31:0] pc, inst;
} if_id_t;
typedef struct packed {
    logic valid;
    logic [31:0] pc, inst, rdata1, rdata2, imm;
    logic [4:0] rs1, rs2, rd;
    ctrl_t ctrl;
} id_ex_t;
typedef struct packed {
    logic valid;
    logic [31:0] pc, inst, alu_out, store_data;
    logic [4:0] rd;
    ctrl_t ctrl;
    logic br_taken;
} ex_mem_t;
typedef struct packed {
    logic valid;
    logic [31:0] pc, inst, alu_out, mem_data, pc4;
    logic [4:0] rd;
    ctrl_t ctrl;
} mem_wb_t;
if_id_t if_id_d, if_id_q;
    id_ex_t id_ex_d, id_ex_q;
    ex_mem_t ex_mem_d, ex_mem_q;
    mem_wb_t mem_wb_d, mem_wb_q;
    ctrl_t ctrl_id;
    logic legal_id;
    logic [31:0] pc4_if, pc_next, inst_if, imm_id, rs1_id, rs2_id;
    logic [31:0] a_selected, a_ex, b_ex, result_ex, data_mem, pc4_mem;
    logic [31:0] alu_or_mem_wb, result_wb;
    logic taken_ex, write_wb, read_mem, write_mem;

    // IF: instruction memory and the sequential PC adder run concurrently.
    pc  u_pc (.i_clk, .i_rst_n, .i_next(pc_next), .o_pc);
    adder u_pc4_if (.i_a(o_pc), .i_b(32'd4), .o_sum(pc4_if));
    mux2 u_pcsel (.i_a(pc4_if), .i_b(ex_mem_q.alu_out),
                  .i_sel(o_redirect), .o_y(pc_next));
    imem  u_imem (
        .i_addr(o_pc), .o_inst(inst_if)
    );
    assign if_id_d = '{valid: 1'b1, pc: o_pc, inst: inst_if};
    if_id_reg u_if_id (.i_clk, .i_rst_n, .i_flush(o_redirect),
                       .i_d(if_id_d), .o_q(if_id_q));

    // ID: control travels with the instruction and its operands.
    control u_control (.i_inst(if_id_q.inst), .o_ctrl(ctrl_id), .o_legal(legal_id));
    imm_gen u_imm (.i_inst(if_id_q.inst), .i_sel(ctrl_id.imm_sel), .o_imm(imm_id));
    regfile u_regfile (
        .i_clk, .i_rst_n, .i_we(write_wb), .i_rd(mem_wb_q.rd), .i_wdata(result_wb),
        .i_rs1(if_id_q.inst[19:15]), .i_rs2(if_id_q.inst[24:20]),
        .o_rdata1(rs1_id), .o_rdata2(rs2_id)
    );
    assign id_ex_d = '{valid: if_id_q.valid && legal_id,
        pc: if_id_q.pc, inst: if_id_q.inst, rdata1: rs1_id, rdata2: rs2_id,
        imm: imm_id, rs1: if_id_q.inst[19:15], rs2: if_id_q.inst[24:20],
        rd: if_id_q.inst[11:7], ctrl: ctrl_id};
    id_ex_reg u_id_ex (.i_clk, .i_rst_n, .i_flush(o_redirect),
                       .i_d(id_ex_d), .o_q(id_ex_q));

    // EX: branch target addition and register comparison are separate paths.
    mux2 u_asel (.i_a(id_ex_q.rdata1), .i_b(id_ex_q.pc),
                 .i_sel(id_ex_q.ctrl.a_pc), .o_y(a_selected));
    mux2 u_azero (.i_a(a_selected), .i_b(32'b0),
                  .i_sel(id_ex_q.ctrl.a_zero), .o_y(a_ex));
    mux2 u_bsel (.i_a(id_ex_q.rdata2), .i_b(id_ex_q.imm),
                 .i_sel(id_ex_q.ctrl.b_imm), .o_y(b_ex));
    alu u_alu (.i_a(a_ex), .i_b(b_ex), .i_op(id_ex_q.ctrl.alu_op), .o_result(result_ex));
    branch_comp u_branch (.i_a(id_ex_q.rdata1), .i_b(id_ex_q.rdata2),
                          .i_ne(id_ex_q.ctrl.branch_ne), .o_taken(taken_ex));
    assign ex_mem_d = '{valid: id_ex_q.valid, pc: id_ex_q.pc, inst: id_ex_q.inst,
        alu_out: result_ex, store_data: id_ex_q.rdata2, rd: id_ex_q.rd,
        ctrl: id_ex_q.ctrl, br_taken: taken_ex};
    // MEM redirect kills the younger EX instruction as well as ID and IF.
    ex_mem_reg u_ex_mem (.i_clk, .i_rst_n, .i_flush(o_redirect),
                         .i_d(ex_mem_d), .o_q(ex_mem_q));

    // MEM: only a valid instruction may redirect or access data memory.
    assign o_redirect = i_rst_n && ex_mem_q.valid &&
        (ex_mem_q.ctrl.jump || (ex_mem_q.ctrl.branch && ex_mem_q.br_taken));
    assign read_mem = i_rst_n && ex_mem_q.valid && ex_mem_q.ctrl.mem_read;
    assign write_mem = i_rst_n && ex_mem_q.valid && ex_mem_q.ctrl.mem_write;
    dmem  u_dmem (
        .i_clk, .i_rst_n, .i_read(read_mem), .i_write(write_mem),
        .i_addr(ex_mem_q.alu_out), .i_wdata(ex_mem_q.store_data), .o_rdata(data_mem)
    );
    adder u_pc4_mem (.i_a(ex_mem_q.pc), .i_b(32'd4), .o_sum(pc4_mem));
    assign mem_wb_d = '{valid: ex_mem_q.valid, pc: ex_mem_q.pc, inst: ex_mem_q.inst,
        alu_out: ex_mem_q.alu_out, mem_data: data_mem, pc4: pc4_mem,
        rd: ex_mem_q.rd, ctrl: ex_mem_q.ctrl};
    mem_wb_reg u_mem_wb (.i_clk, .i_rst_n, .i_flush(1'b0),
                         .i_d(mem_wb_d), .o_q(mem_wb_q));

    // WB: preserve the redirecting instruction's link write and older results.
    mux2 u_wb_mem (.i_a(mem_wb_q.alu_out), .i_b(mem_wb_q.mem_data),
                   .i_sel(mem_wb_q.ctrl.wb_sel == WB_MEM), .o_y(alu_or_mem_wb));
    mux2 u_wb_link (.i_a(alu_or_mem_wb), .i_b(mem_wb_q.pc4),
                    .i_sel(mem_wb_q.ctrl.wb_sel == WB_PC4), .o_y(result_wb));
    assign o_retire_valid = i_rst_n && mem_wb_q.valid;
    assign write_wb = o_retire_valid && mem_wb_q.ctrl.reg_write && (mem_wb_q.rd != 0);
    assign o_retire_we = write_wb;
    assign o_retire_pc = mem_wb_q.pc;
    assign o_retire_inst = mem_wb_q.inst;
    assign o_retire_rd = mem_wb_q.rd;
    assign o_retire_data = result_wb;
`line 1 "rtl/components/riscv5_top.sv" 0
endmodule

`default_nettype wire
