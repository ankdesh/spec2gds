module evaluation_tb;
  localparam int W=@@WIDTH@@;
  logic clk=0, reset=1;
  logic [W-1:0] din=0, dout, first=0, expected=0;
  @@TOP@@ dut (.clk(clk), .reset(reset), .din(din), .dout(dout));
  always #5 clk=~clk;
  initial begin
    for(int i=0;i<100;i++) begin
      @(negedge clk); reset=(i%29==0); din=W'($urandom);
      @(posedge clk); expected=reset ? '0 : first; first=reset ? '0 : din;
      #1; if(dout !== expected) $fatal(1,"registered pipeline latency/reset failed");
    end
    $display("EVALUATION_PASS"); $finish;
  end
endmodule
