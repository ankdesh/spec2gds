// One reusable brightness channel. PWM_BITS must be at least 1.
module pwm_channel #(
    parameter int unsigned PWM_BITS = 8
) (
    input  logic              clk,
    input  logic              rst,
    input  logic [PWM_BITS:0]  duty,
    output logic              pwm
);
logic [PWM_BITS-1:0] phase;

always_ff @(posedge clk) begin
    if (rst)
        phase <= '0;
    else
        phase <= phase + 1'b1;
end

// The extra duty bit allows both exactly 0% and exactly 100% brightness.
// Values above the period also produce a continuously high output.
assign pwm = !rst && ({1'b0, phase} < duty);
endmodule
