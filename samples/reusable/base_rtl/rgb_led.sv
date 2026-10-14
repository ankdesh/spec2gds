// Reuse the same PWM circuit for three independently controlled colors.
module rgb_led #(
    parameter int unsigned PWM_BITS = 8
) (
    input  logic             clk,
    input  logic             rst,
    input  logic [PWM_BITS:0] red_duty,
    input  logic [PWM_BITS:0] green_duty,
    input  logic [PWM_BITS:0] blue_duty,
    output logic [2:0]        rgb_pwm
);
// Packed output order: {red, green, blue}.
pwm_channel #(.PWM_BITS(PWM_BITS)) red (
    .clk(clk), .rst(rst), .duty(red_duty), .pwm(rgb_pwm[2])
);
pwm_channel #(.PWM_BITS(PWM_BITS)) green (
    .clk(clk), .rst(rst), .duty(green_duty), .pwm(rgb_pwm[1])
);
pwm_channel #(.PWM_BITS(PWM_BITS)) blue (
    .clk(clk), .rst(rst), .duty(blue_duty), .pwm(rgb_pwm[0])
);
endmodule
