`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module top_design_top;

    wire [31:0] net_1;

    new_component new_comp1 (
        .clk('0),
        .rst_n('0),
        .data_in('0),
        .valid_in('0),
        .data_out(net_1)
    );

    new_component new_component (
        .clk('0),
        .rst_n('0),
        .data_in(net_1),
        .valid_in('0),
        .data_out()
    );
endmodule

`default_nettype wire
