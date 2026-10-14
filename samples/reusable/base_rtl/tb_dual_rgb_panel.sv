module tb_dual_rgb_panel;
    timeunit 1ns;
    timeprecision 1ps;

    // Small period keeps simulation short; the RTL defaults to 8-bit PWM.
    localparam int unsigned PWM_BITS = 4;
    localparam int unsigned PERIOD = 1 << PWM_BITS;
    bit clk;
    logic rst = 1;
    logic [PWM_BITS:0] duty [6];
    logic [2:0] status_rgb, activity_rgb;
    logic [5:0] outputs;
    int unsigned high_cycles [6];

    initial begin
        clk = 0;
        forever #5 clk = ~clk;
    end
    assign outputs = {activity_rgb, status_rgb};

    dual_rgb_panel #(.PWM_BITS(PWM_BITS)) dut (
        .clk(clk), .rst(rst),
        .status_red(duty[2]), .status_green(duty[1]), .status_blue(duty[0]),
        .activity_red(duty[5]), .activity_green(duty[4]), .activity_blue(duty[3]),
        .status_rgb(status_rgb), .activity_rgb(activity_rgb)
    );

    initial begin
        duty = '{0, 1, 4, 8, 15, 16};
        repeat (2) @(posedge clk);
        #1;
        if (outputs !== 6'b0) $fatal(1, "Outputs must be off during reset");
        @(negedge clk);
        rst = 0;

        // Check two different palettes. Different values on all six channels
        // expose accidental wiring between colors or between the two LEDs.
        for (int palette = 0; palette < 2; palette++) begin
            foreach (high_cycles[channel]) high_cycles[channel] = 0;
            repeat (PERIOD) begin
                @(posedge clk);
                #1;
                foreach (high_cycles[channel]) begin
                    if (outputs[channel]) high_cycles[channel]++;
                end
            end
            foreach (high_cycles[channel]) begin
                if (high_cycles[channel] !=
                    ((int'(duty[channel]) > PERIOD) ? PERIOD : int'(duty[channel])))
                    $fatal(1, "Palette %0d channel %0d: got %0d high cycles, duty=%0d",
                           palette, channel, high_cycles[channel], duty[channel]);
            end
            @(negedge clk);
            duty = '{16, 12, 8, 4, 0, 31};
        end

        // Reset after running, then verify that all reused counters realign.
        rst = 1;
        @(posedge clk);
        #1;
        if (outputs !== 6'b0) $fatal(1, "Reset must blank both LEDs");
        @(negedge clk);
        duty = '{default: 1};
        rst = 0;
        #1;
        if (outputs !== 6'b111111) $fatal(1, "Reset must clear every phase counter");
        @(posedge clk);
        #1;
        if (outputs !== 6'b0) $fatal(1, "One-cycle duty must fall after phase zero");

        $display("PASS: six independent PWM channels, palette updates, saturation, and reset");
        $finish;
    end

    initial begin
        #10000;
        $fatal(1, "Simulation timed out");
    end
endmodule
