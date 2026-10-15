`include "riscv_defs.svh"
module tb_units;
    logic clk, rst_n = 1;
    logic [31:0] a, b, result, instruction, immediate;
    logic [7:0] a8, b8, sum8, product8, pc8;
    alu_op_t op;
    imm_sel_t imm_sel;
    ctrl_t ctrl;
    logic legal, ne, taken;
    logic mem_read, mem_write;
    logic [31:0] mem_addr, mem_wdata, mem_rdata;
    logic flush;
    if_id_t pipe_d, pipe_q;
    logic [63:0] wide_product;
    logic reg_we;
    logic [4:0] reg_rs1, reg_rs2, reg_rd;
    logic [31:0] reg_data, reg_a, reg_b;
    logic [31:0] random_state = 32'h1badf00d;
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    alu u_alu (.i_a(a), .i_b(b), .i_op(op), .o_result(result));
    adder #(.WIDTH(8)) u_add8 (.i_a(a8), .i_b(b8), .o_sum(sum8));
    multiplier #(.WIDTH(8)) u_mul8 (.i_a(a8), .i_b(b8), .o_product(product8));
    pc #(.WIDTH(8), .RESET_PC(8'h80)) u_pc (
        .i_clk(clk), .i_rst_n(rst_n), .i_next(a8), .o_pc(pc8)
    );
    branch_comp u_branch (.i_a(a), .i_b(b), .i_ne(ne), .o_taken(taken));
    control u_control (.i_inst(instruction), .o_ctrl(ctrl), .o_legal(legal));
    imm_gen u_imm (.i_inst(instruction), .i_sel(imm_sel), .o_imm(immediate));
    dmem #(.DEPTH(3)) u_dmem (
        .i_clk(clk), .i_rst_n(rst_n), .i_read(mem_read), .i_write(mem_write),
        .i_addr(mem_addr), .i_wdata(mem_wdata), .o_rdata(mem_rdata)
    );
    pipe_reg #(.T(if_id_t)) u_pipe (
        .i_clk(clk), .i_rst_n(rst_n), .i_flush(flush), .i_d(pipe_d), .o_q(pipe_q)
    );
    regfile u_regfile (
        .i_clk(clk), .i_rst_n(rst_n), .i_we(reg_we), .i_rs1(reg_rs1),
        .i_rs2(reg_rs2), .i_rd(reg_rd), .i_wdata(reg_data),
        .o_rdata1(reg_a), .o_rdata2(reg_b)
    );

    task automatic check_imm(input logic [31:0] word_value,
                             input imm_sel_t sel, input logic [31:0] expected);
        instruction = word_value;
        imm_sel = sel;
        #1;
        if (immediate !== expected) $fatal(1, "Immediate mismatch %h", word_value);
    endtask

    task automatic reject(input logic [31:0] word_value);
        instruction = word_value;
        #1;
        if (legal || ctrl.reg_write || ctrl.mem_read || ctrl.mem_write || ctrl.branch || ctrl.jump)
            $fatal(1, "Illegal encoding has side effects: %h", word_value);
    endtask

    initial begin
        a = 0; b = 0; a8 = 0; b8 = 0; op = ALU_ADD;
        instruction = 0; imm_sel = IMM_I; ne = 0;
        mem_read = 0; mem_write = 0; mem_addr = 0; mem_wdata = 0;
        flush = 0; pipe_d = '0;
        reg_we = 0; reg_rs1 = 0; reg_rs2 = 0; reg_rd = 0; reg_data = 0;
        #1; rst_n = 0;
        #1;
        if (pipe_q !== '0 || pc8 !== 8'h80) $fatal(1, "Parameterized reset failed");
        @(negedge clk); rst_n = 1;
        // Deterministic varied operands; full-width arithmetic and low product.
        for (int n = 0; n < 256; n++) begin
            random_state = {random_state[30:0], random_state[31] ^ random_state[21] ^ random_state[1] ^ random_state[0]};
            a = random_state;
            b = ~random_state ^ (32'(n) << 16);
            a8 = 8'(n); b8 = 8'(255 - n);
            op = ALU_ADD;
            #1;
            if (result !== (a + b) || sum8 !== 8'(a8 + b8)) $fatal(1, "Adder mismatch");
            op = ALU_MUL;
            wide_product = 64'($signed(a)) * 64'($signed(b));
            #1;
            if (result !== wide_product[31:0] || product8 !== 8'(a8 * b8))
                $fatal(1, "Multiplier mismatch");
        end
        a = 32'hffffffff; b = 1; op = ALU_ADD; #1;
        if (result !== 0) $fatal(1, "Addition wrap failed");
        a = 32'h80000000; b = 32'hffffffff; op = ALU_MUL; #1;
        if (result !== 32'h80000000) $fatal(1, "Signed product truncation failed");
        ne = 0; #1; if (taken) $fatal(1, "BEQ unequal");
        ne = 1; #1; if (!taken) $fatal(1, "BNE unequal");
        b = a; #1; if (taken) $fatal(1, "BNE equal");
        ne = 0; #1; if (!taken) $fatal(1, "BEQ equal");

        check_imm(32'h80000000, IMM_I, 32'hfffff800);
        check_imm(32'h7ff00000, IMM_I, 32'h000007ff);
        check_imm(32'hfe000e00, IMM_S, 32'hfffffffc);
        check_imm(32'h7e000f80, IMM_S, 32'h000007ff);
        check_imm(32'h80000000, IMM_B, 32'hfffff000);
        check_imm(32'h7e000f80, IMM_B, 32'h00000ffe);
        check_imm(32'h80000000, IMM_J, 32'hfff00000);
        check_imm(32'h7ffff000, IMM_J, 32'h000ffffe);
        check_imm(32'habcde037, IMM_U, 32'habcde000);
        reject(32'hffffffff); // unknown opcode
        reject(32'h402081b3); // SUB
        reject(32'h022091b3); // MULH
        reject(32'h0020e1b3); // OR
        reject(32'h00109193); // SLLI
        reject(32'h00008183); // LB
        reject(32'h00100023); // SB
        reject(32'h0020c063); // BLT
        reject(32'h00000067); // JALR
        reject(32'h00000073); // ECALL
        instruction = 32'h12345037; #1;
        if (!legal || !ctrl.a_zero || !ctrl.b_imm || !ctrl.reg_write)
            $fatal(1, "LUI control failed");

        @(negedge clk);
        pipe_d = '{valid: 1'b1, pc: 32'h1234, inst: 32'h5678};
        @(posedge clk); #1;
        if (pipe_q !== pipe_d) $fatal(1, "Packed pipeline capture failed");
        @(negedge clk); flush = 1;
        @(posedge clk); #1;
        if (pipe_q !== '0) $fatal(1, "Pipeline flush failed");

        @(negedge clk);
        reg_rd = 31; reg_rs1 = 31; reg_rs2 = 31; reg_data = 32'h98765432; reg_we = 1;
        #1;
        if (reg_a !== 0 || reg_b !== 0) $fatal(1, "Unexpected register bypass");
        @(posedge clk); #1;
        if (reg_a !== reg_data || reg_b !== reg_data) $fatal(1, "Register read/write failed");
        @(negedge clk); reg_rd = 0; reg_rs1 = 0;
        @(posedge clk); #1;
        if (reg_a !== 0 || reg_b !== reg_data) $fatal(1, "x0 protection failed");
        @(negedge clk); reg_we = 0;

        // Non-power-of-two memory depth must not alias out-of-range addresses.
        @(negedge clk);
        mem_addr = 8; mem_wdata = 32'hfeedbeef; mem_write = 1; mem_read = 1;
        @(posedge clk); #1;
        if (mem_rdata !== 32'hfeedbeef) $fatal(1, "Last memory word failed");
        @(negedge clk); mem_addr = 12; mem_wdata = 99;
        @(posedge clk); #1;
        if (mem_rdata !== 0) $fatal(1, "Out-of-range memory read failed");
        @(negedge clk); mem_addr = 9;
        @(posedge clk); #1;
        if (mem_rdata !== 0) $fatal(1, "Unaligned memory read failed");
        @(negedge clk); mem_addr = 8; mem_write = 0;
        #1;
        if (mem_rdata !== 32'hfeedbeef) $fatal(1, "Invalid write aliased valid memory");
        mem_read = 0; #1;
        if (mem_rdata !== 0) $fatal(1, "Memory read enable failed");
        rst_n = 0; mem_read = 1; #1;
        if (mem_rdata !== 0 || u_dmem.mem[2] !== 0 || reg_b !== 0)
            $fatal(1, "Memory/register reset failed");
        $display("PASS reusable blocks, immediate formats, decode rejection, flush, and memory bounds");
        $finish;
    end
endmodule
