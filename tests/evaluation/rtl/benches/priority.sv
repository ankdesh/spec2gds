module evaluation_tb;
  logic [7:0] request;
  logic [2:0] index;
  logic valid;
  @@TOP@@ dut (.*);
  initial begin
    for(int value=0;value<256;value++) begin
      int expected;
      expected=0; request=8'(value);
      for(int bitno=0;bitno<8;bitno++) if(request[bitno]) expected=bitno;
      #1;
      if(valid !== (value!=0) || index !== 3'(expected)) $fatal(1,"priority encoder failed");
    end
    $display("EVALUATION_PASS"); $finish;
  end
endmodule
