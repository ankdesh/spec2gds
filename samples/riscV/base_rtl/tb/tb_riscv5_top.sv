`include "riscv_defs.svh"
module tb_riscv5_top;
    logic clk;
    logic rst_n = 1;
    logic [31:0] pc_if, retire_pc, inst, value;
    logic [4:0] rd;
    logic valid, we, redirect;
    logic [31:0] ref_regs [0:31];
    logic [31:0] ref_mem [0:255];
    logic [31:0] program_words [0:255];
    logic [31:0] ref_pc;
    int retired, stores, expected_stores, redirects, cycles;
    string trace_path;

    riscv5_top dut (
        .i_clk(clk), .i_rst_n(rst_n), .o_pc(pc_if),
        .o_retire_valid(valid), .o_retire_we(we), .o_retire_pc(retire_pc),
        .o_retire_inst(inst), .o_retire_data(value), .o_retire_rd(rd),
        .o_redirect(redirect)
    );
    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end

    // Sequential architectural reference, independent of pipeline/control types.
    task automatic check_retirement;
        logic [31:0] instruction, a, b, immediate, result, next_pc, address;
        logic expected_we;
        int dest;
        instruction = program_words[ref_pc >> 2];
        if (retire_pc !== ref_pc || inst !== instruction)
            $fatal(1, "Retirement mismatch: expected pc=%h inst=%h, got pc=%h inst=%h",
                   ref_pc, instruction, retire_pc, inst);
        a = ref_regs[instruction[19:15]];
        b = ref_regs[instruction[24:20]];
        dest = int'(instruction[11:7]);
        next_pc = ref_pc + 4;
        result = 0;
        expected_we = 0;
        case (instruction[6:0])
            7'h33: begin
                result = instruction[25] ? a * b : a + b;
                expected_we = 1;
            end
            7'h13: begin
                result = a + {{20{instruction[31]}}, instruction[31:20]};
                expected_we = 1;
            end
            7'h37: begin result = instruction & 32'hfffff000; expected_we = 1; end
            7'h03: begin
                address = a + {{20{instruction[31]}}, instruction[31:20]};
                result = ref_mem[address >> 2];
                expected_we = 1;
            end
            7'h23: begin
                immediate = {{20{instruction[31]}}, instruction[31:25], instruction[11:7]};
                address = a + immediate;
                ref_mem[address >> 2] = b;
                expected_stores++;
            end
            7'h63: begin
                immediate = {{19{instruction[31]}}, instruction[31], instruction[7],
                             instruction[30:25], instruction[11:8], 1'b0};
                if (instruction[12] ? a != b : a == b) next_pc = ref_pc + immediate;
            end
            7'h6f: begin
                immediate = {{11{instruction[31]}}, instruction[31], instruction[19:12],
                             instruction[20], instruction[30:21], 1'b0};
                next_pc = ref_pc + immediate;
                result = ref_pc + 4;
                expected_we = 1;
            end
            default: $fatal(1, "Unsupported instruction in reference: %h", instruction);
        endcase
        expected_we = expected_we && (dest != 0);
        if (we !== expected_we) $fatal(1, "Write enable mismatch at pc=%h", ref_pc);
        if (expected_we) begin
            if (int'(rd) != dest || value !== result)
                $fatal(1, "Write mismatch at pc=%h: x%0d expected=%h got x%0d=%h",
                       ref_pc, dest, result, rd, value);
            ref_regs[dest] = result;
        end
        ref_pc = next_pc;
        retired++;
    endtask

    task automatic reset_core;
        @(negedge clk);
        rst_n = 0;
        ref_pc = 0;
        retired = 0;
        stores = 0;
        expected_stores = 0;
        redirects = 0;
        cycles = 0;
        foreach (ref_regs[n]) ref_regs[n] = 0;
        foreach (ref_mem[n]) ref_mem[n] = 0;
        #1;
        if (valid || redirect || we || pc_if !== 0) $fatal(1, "Asynchronous reset failed");
        repeat (2) @(negedge clk);
        rst_n = 1;
    endtask

    task automatic expect_reg(input int index, input logic [31:0] expected);
        if (dut.u_regfile.regs[index] !== expected)
            $fatal(1, "x%0d: expected %h got %h", index, expected, dut.u_regfile.regs[index]);
    endtask

    initial forever begin
        @(posedge clk);
        if (rst_n) begin
            cycles++;
            if (cycles > 1000) $fatal(1, "Program timed out");
            if (dut.write_mem) stores++;
            if (valid) check_retirement();
            if (redirect) begin
                redirects++;
                #1;
                if (dut.if_id_q.valid || dut.id_ex_q.valid || dut.ex_mem_q.valid)
                    $fatal(1, "MEM redirect did not flush all three younger instructions");
                if (!dut.mem_wb_q.valid) $fatal(1, "Redirecting instruction was lost");
            end
        end
    end

    initial begin
        foreach (program_words[n]) program_words[n] = 32'h00000013;
        $readmemh("tb/programs/core_test.hex", program_words);
        if ($value$plusargs("trace=%s", trace_path)) begin
            $dumpfile(trace_path);
            $dumpvars(0, tb_riscv5_top);
        end
        reset_core();
        // Reset with instructions in flight, then execute twice from reset.
        repeat (8) @(negedge clk);
        for (int run = 0; run < 2; run++) begin
            reset_core();
            while (ref_regs[31] != 1) @(negedge clk);
            foreach (ref_regs[n]) expect_reg(n, ref_regs[n]);
            foreach (ref_mem[n]) begin
                if (dut.u_dmem.mem[n] !== ref_mem[n])
                    $fatal(1, "Memory mismatch at word %0d", n);
            end
            expect_reg(0, 0);
            expect_reg(1, 10);
            expect_reg(2, 32'hfffffffc);
            expect_reg(3, 6);
            expect_reg(4, 32'hffffffd8);
            expect_reg(5, 6);
            expect_reg(6, 32'hffffffd8);
            expect_reg(7, 100);
            expect_reg(8, 1);
            expect_reg(9, 0);
            expect_reg(10, 32'h00000078);
            expect_reg(11, 0);
            expect_reg(12, 32'h12345000);
            expect_reg(13, 32'hffffffde);
            expect_reg(14, 32'hffffff10);
            expect_reg(15, 7);
            expect_reg(18, 32'h80000000);
            expect_reg(19, 0);
            expect_reg(20, 0);
            expect_reg(21, 77);
            expect_reg(22, 32'h00000078);
            expect_reg(24, 32'hffffffde);
            expect_reg(25, 32'hffffffe8);
            expect_reg(26, 0);
            if (stores != expected_stores || stores != 3)
                $fatal(1, "Unexpected store count: %0d expected %0d", stores, expected_stores);
            if (redirects < 8) $fatal(1, "Missing control-flow coverage");
            $display("PASS program run %0d: %0d retirements, %0d stores, %0d redirects, %0d cycles",
                     run + 1, retired, stores, redirects, cycles);
        end
        $display("ALL TESTS PASSED");
        $finish;
    end
endmodule
