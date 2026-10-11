module evaluation_tb;
  localparam int W=@@WIDTH@@, D=@@DEPTH@@;
  logic wclk=0, rclk=0, wrstn=0, rrstn=0, winc=0, rinc=0;
  logic [W-1:0] wdata=0, rdata;
  logic wfull, rempty;
  @@TOP@@ dut (.wclk(wclk), .rclk(rclk), .wrstn(wrstn), .rrstn(rrstn), .winc(winc), .rinc(rinc), .wdata(wdata), .rdata(rdata), .wfull(wfull), .rempty(rempty));
  always #5 wclk=~wclk;
  always #7 rclk=~rclk;
  task write_word(input logic [W-1:0] value);
    @(negedge wclk);
    while(wfull) @(negedge wclk);
    wdata=value; winc=1;
    @(negedge wclk); winc=0;
  endtask
  task read_word(input logic [W-1:0] expected);
    @(negedge rclk);
    while(rempty) @(negedge rclk);
    rinc=1;
    @(posedge rclk); #1;
    if(rdata !== expected) $fatal(1,"FIFO ordering failed: got=%h expected=%h",rdata,expected);
    @(negedge rclk); rinc=0;
  endtask
  task settle;
    repeat (8) @(negedge rclk);
    repeat (8) @(negedge wclk);
  endtask
  initial begin
    repeat (3) @(negedge wclk); wrstn=1;
    repeat (3) @(negedge rclk); rrstn=1;
    settle();
    if(!rempty || wfull) $fatal(1,"reset boundary flags failed");
    // Empty read must leave pointers unchanged.
    @(negedge rclk); rinc=1; repeat(2) @(negedge rclk); rinc=0;
    write_word(W'(85)); settle();
    if(rempty) $fatal(1,"single accepted write never became visible");
    read_word(W'(85)); settle();
    if(!rempty) $fatal(1,"single accepted read did not empty FIFO");
    for(int round=0;round<4;round++) begin
      for(int i=0;i<D;i++) write_word(W'(round*D+i));
      settle(); if(!wfull) $fatal(1,"full boundary missing");
      @(negedge wclk); wdata='1; winc=1; repeat(2) @(negedge wclk); winc=0;
      for(int i=0;i<D;i++) read_word(W'(round*D+i));
      settle(); if(!rempty || wfull) $fatal(1,"empty boundary or wrapped pointers failed");
    end
    // Concurrent transfers exercise CDC while avoiding full/empty ambiguous edges.
    for(int i=0;i<D/2;i++) write_word(W'(i));
    settle();
    fork
      begin for(int i=0;i<D;i++) write_word(W'(D/2+i)); end
      begin for(int i=0;i<D;i++) read_word(W'(i)); end
    join
    settle(); for(int i=D;i<D+D/2;i++) read_word(W'(i));
    settle(); if(!rempty) $fatal(1,"concurrent unequal-clock transfers lost ordering");
    $display("EVALUATION_PASS"); $finish;
  end
  initial begin #100000; $fatal(1,"FIFO timeout"); end
endmodule
