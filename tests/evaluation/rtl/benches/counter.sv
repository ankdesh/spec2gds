module evaluation_tb;
  localparam int W = @@WIDTH@@;
  logic clk=0, reset=1, up_down=1;
  logic [W-1:0] count, expected=0;
  @@TOP@@ dut (.*);
  always #5 clk=~clk;
  task step(input bit rst, input bit direction);
    @(negedge clk); reset=rst; up_down=direction;
    @(posedge clk);
    expected = rst ? '0 : direction ? expected+W'(1) : expected-W'(1);
    #1;
    if (count !== expected) $fatal(1,"counter reset/direction/wrap failed: got=%h expected=%h",count,expected);
  endtask
  initial begin
    repeat (2) @(negedge clk);
    step(1,1); step(0,0); step(0,1);
    for(int i=0; i<300; i++) step(i%73==0, 1'(i%7!=0));
    step(1,0); step(0,0); step(0,0); step(0,1);
    $display("EVALUATION_PASS"); $finish;
  end
endmodule
