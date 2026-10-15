`ifndef RISCV_DEFS_SVH
`define RISCV_DEFS_SVH

// Compilation-unit types: deliberately no package or import statements.
localparam int XLEN = 32;
localparam int REG_ADDR = 5;
localparam int NREG = 32;
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
    logic [XLEN-1:0] pc, inst;
} if_id_t;
typedef struct packed {
    logic valid;
    logic [XLEN-1:0] pc, inst, rdata1, rdata2, imm;
    logic [REG_ADDR-1:0] rs1, rs2, rd;
    ctrl_t ctrl;
} id_ex_t;
typedef struct packed {
    logic valid;
    logic [XLEN-1:0] pc, inst, alu_out, store_data;
    logic [REG_ADDR-1:0] rd;
    ctrl_t ctrl;
    logic br_taken;
} ex_mem_t;
typedef struct packed {
    logic valid;
    logic [XLEN-1:0] pc, inst, alu_out, mem_data, pc4;
    logic [REG_ADDR-1:0] rd;
    ctrl_t ctrl;
} mem_wb_t;

`endif
