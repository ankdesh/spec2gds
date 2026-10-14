// Toy instrument panel: independent system-status and activity indicators.
module dual_rgb_panel #(
    parameter int unsigned PWM_BITS = 8
) (
    input  logic             clk,
    input  logic             rst,
    input  logic [PWM_BITS:0] status_red,
    input  logic [PWM_BITS:0] status_green,
    input  logic [PWM_BITS:0] status_blue,
    input  logic [PWM_BITS:0] activity_red,
    input  logic [PWM_BITS:0] activity_green,
    input  logic [PWM_BITS:0] activity_blue,
    output logic [2:0]        status_rgb,
    output logic [2:0]        activity_rgb
);
rgb_led #(.PWM_BITS(PWM_BITS)) status_led (
    .clk(clk), .rst(rst),
    .red_duty(status_red), .green_duty(status_green), .blue_duty(status_blue),
    .rgb_pwm(status_rgb)
);
rgb_led #(.PWM_BITS(PWM_BITS)) activity_led (
    .clk(clk), .rst(rst),
    .red_duty(activity_red), .green_duty(activity_green), .blue_duty(activity_blue),
    .rgb_pwm(activity_rgb)
);
endmodule
