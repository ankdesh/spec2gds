`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module imm_gen (
    input logic [31:0] i_inst,
    input logic [2:0] i_sel,
    output logic [31:0] o_imm
);

    // SystemVerilog section: section_sv_imm_gen
`line 1 "annotations/entity-sections/sv/section_sv_imm_gen.sv" 0
logic signed [31:0] imm;
    always_comb begin
        case (i_sel)
            3'd0: imm = {{20{i_inst[31]}}, i_inst[31:20]};
            3'd1: imm = {{20{i_inst[31]}}, i_inst[31:25], i_inst[11:7]};
            3'd2: imm = {{19{i_inst[31]}}, i_inst[31], i_inst[7],
                          i_inst[30:25], i_inst[11:8], 1'b0};
            3'd3: imm = {i_inst[31:12], 12'b0};
            3'd4: imm = {{11{i_inst[31]}}, i_inst[31], i_inst[19:12],
                          i_inst[20], i_inst[30:21], 1'b0};
            default: imm = '0;
        endcase
        o_imm = 32'(imm);
    end
`line 1 "rtl/components/imm_gen.sv" 0
endmodule

`default_nettype wire
