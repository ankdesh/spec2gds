`default_nettype none

// Generated from IP-XACT structure and stored SystemVerilog module-body semantics.
module new_component (
    input logic clk,
    input logic rst_n,
    input logic [31:0] data_in,
    input logic valid_in,
    output logic [31:0] data_out
);

    // SystemVerilog section: section_sv_component_new_component_ac94282c1aeb4b178807e77e8f10c280
`line 1 "annotations/entity-sections/sv/section_sv_component_new_component_ac94282c1aeb4b178807e77e8f10c280.sv" 0
logic [31:0] data_pipe;
logic valid_pipe;

always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
        data_pipe <= '0;
        valid_pipe <= 1'b0;
        data_out <= '0;
    end else begin
        valid_pipe <= valid_in;
        if (valid_in) begin
            data_pipe <= data_in;
        end
        if (valid_pipe) begin
            data_out <= data_pipe;
        end
    end
end
`line 1 "rtl/components/new_component.sv" 0

    wire _unused_ok;
    assign _unused_ok = 1'b0 && &{1'b0, clk, rst_n, data_in, valid_in, 1'b0};
endmodule

`default_nettype wire
