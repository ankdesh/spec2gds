module evaluation_tb;
  localparam int W = @@WIDTH@@;
  logic [W-1:0] a, b, sum;
  logic cin, cout;
  logic [W:0] expected;
  @@TOP@@ dut (.*);
  initial begin
    for (int i=0; i<512; i++) begin
      a = W'($urandom); b = W'($urandom); cin = 1'(i);
      if (i<W) begin a = (W'(1)<<i)-1; b = 0; cin = 1; end
      if (i==W) begin a='1; b='1; cin=1; end
      expected = {1'b0,a}+{1'b0,b}+{{W{1'b0}},cin};
      #1;
      if ({cout,sum} !== expected) $fatal(1,"carry propagation failed: a=%h b=%h cin=%b got=%h expected=%h",a,b,cin,{cout,sum},expected);
    end
    $display("EVALUATION_PASS"); $finish;
  end
endmodule
