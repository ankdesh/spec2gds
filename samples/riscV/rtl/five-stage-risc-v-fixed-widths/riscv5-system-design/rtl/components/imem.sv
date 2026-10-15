`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module imem (
    input logic [31:0] i_addr,
    output logic [31:0] o_inst
);

    // SystemVerilog section: section_sv_imem
`line 1 "annotations/entity-sections/sv/section_sv_imem.sv" 0

    logic [31:0] mem [0:255];
    // Initialized ROM; a synthesis flow must support memory initialization.
    initial begin
        for (int n = 0; n < 256; n++) mem[n] = 32'(32'h00000013);
            mem[0] = 32'h00a00093;
    mem[1] = 32'hffc00113;
    mem[2] = 32'h00000013;
    mem[3] = 32'h00000013;
    mem[4] = 32'h00000013;
    mem[5] = 32'h002081b3;
    mem[6] = 32'h02208233;
    mem[7] = 32'h00000013;
    mem[8] = 32'h00000013;
    mem[9] = 32'h00000013;
    mem[10] = 32'h00302023;
    mem[11] = 32'h00402223;
    mem[12] = 32'h00002283;
    mem[13] = 32'h00402303;
    mem[14] = 32'h06400393;
    mem[15] = 32'h00000013;
    mem[16] = 32'h00000013;
    mem[17] = 32'h00000013;
    mem[18] = 32'h10628e63;
    mem[19] = 32'h00100413;
    mem[20] = 32'h00629863;
    mem[21] = 32'h00102423;
    mem[22] = 32'h06300493;
    mem[23] = 32'h108005ef;
    mem[24] = 32'h00328863;
    mem[25] = 32'h05800493;
    mem[26] = 32'h00102623;
    mem[27] = 32'h05800593;
    mem[28] = 32'h0e329a63;
    mem[29] = 32'h0100056f;
    mem[30] = 32'h00102823;
    mem[31] = 32'h04d00593;
    mem[32] = 32'h0e40006f;
    mem[33] = 32'h12345637;
    mem[34] = 32'h004186b3;
    mem[35] = 32'h02418733;
    mem[36] = 32'h03700013;
    mem[37] = 32'h02208033;
    mem[38] = 32'h00700793;
    mem[39] = 32'h80000837;
    mem[40] = 32'hfff00893;
    mem[41] = 32'h00000013;
    mem[42] = 32'h00000013;
    mem[43] = 32'h00000013;
    mem[44] = 32'h03180933;
    mem[45] = 32'h010809b3;
    mem[46] = 32'h00300a13;
    mem[47] = 32'h00000013;
    mem[48] = 32'h00000013;
    mem[49] = 32'h00000013;
    mem[50] = 32'hfffa0a13;
    mem[51] = 32'h00000013;
    mem[52] = 32'h00000013;
    mem[53] = 32'h00000013;
    mem[54] = 32'hfe0a18e3;
    mem[55] = 32'h04d00a93;
    mem[56] = 32'h0100006f;
    mem[57] = 32'h00102a23;
    mem[58] = 32'h04200493;
    mem[59] = 32'h04200593;
    mem[60] = 32'h00050b13;
    mem[61] = 32'h00c00b93;
    mem[62] = 32'h00000013;
    mem[63] = 32'h00000013;
    mem[64] = 32'h00000013;
    mem[65] = 32'hfedbae23;
    mem[66] = 32'hffcbac03;
    mem[67] = 32'h00000013;
    mem[68] = 32'h00000013;
    mem[69] = 32'h00000013;
    mem[70] = 32'h001c0cb3;
    mem[71] = 32'h00200d13;
    mem[72] = 32'h00000013;
    mem[73] = 32'h00000013;
    mem[74] = 32'h00000013;
    mem[75] = 32'hfffd0d13;
    mem[76] = 32'h00000013;
    mem[77] = 32'h00000013;
    mem[78] = 32'h00000013;
    mem[79] = 32'h000d0a63;
    mem[80] = 32'hfedff06f;
    mem[81] = 32'h00102c23;
    mem[82] = 32'h03700493;
    mem[83] = 32'h03700593;
    mem[84] = 32'h00100f93;
    mem[85] = 32'h0000006f;
    mem[86] = 32'h00000013;
    mem[87] = 32'h00000013;
    mem[88] = 32'h00000013;
    mem[89] = 32'h02c00493;
    mem[90] = 32'hfedff06f;
    end
    always_comb begin
        o_inst = 32'(32'h00000013);
        if ((i_addr[1:0] == '0) && ((i_addr >> 2) < 256))
            o_inst = mem[i_addr >> 2];
    end
`line 1 "rtl/components/imem.sv" 0
endmodule

`default_nettype wire
