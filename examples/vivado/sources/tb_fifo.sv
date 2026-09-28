`timescale 1ns/1ps
module tb_fifo;
  parameter integer CORRUPT=0;
  reg wr_clk=0, rd_clk=0, rst=0, wr_valid=0, rd_ready=0;
  reg [15:0] wr_data=0;
  wire wr_ready, rd_valid, full, empty, wr_rst_busy, rd_rst_busy;
  wire [15:0] rd_data;
  logic [15:0] expected_q[$];
  logic [15:0] expected;
  integer written=0, read_count=0, discarded=0, max_pending=0;
  integer reset_count=0, full_cycles=0, empty_cycles=0, paused_cycles=0;
  integer sequence_number=0, fd;
  bit active=0;
  always #6.25 wr_clk=~wr_clk;
  always #5 rd_clk=~rd_clk;
  fifo_top #(.CORRUPT(CORRUPT)) dut(.*);
  task fail(input string why);
    begin
      fd=$fopen("fifo_result.txt","w");
      $fdisplay(fd,"FAIL reason=%s written=%0d read=%0d discarded=%0d pending=%0d corrupt=%0d",why,written,read_count,discarded,expected_q.size(),CORRUPT);
      $fclose(fd); $fatal(1,"FIFO_FAIL %s",why);
    end
  endtask
  // Reference model records external accepted transfers; it does not reproduce
  // FIFO pointers, Gray encodings, synchronization logic, or implementation state.
  // 6.25+12.5*n and 5+10*n never coincide, so queue update ordering is unambiguous.
  always @(posedge wr_clk) if(active && !rst) begin
    if(wr_valid && wr_ready) begin
      expected_q.push_back(wr_data); written=written+1;
      if(expected_q.size()>max_pending) max_pending=expected_q.size();
    end
    if(full === 1) full_cycles=full_cycles+1;
    if(wr_rst_busy && wr_ready) fail("ready during write reset");
  end
  always @(posedge rd_clk) if(active && !rst) begin
    if(empty === 1) empty_cycles=empty_cycles+1;
    if(rd_valid && !rd_ready) paused_cycles=paused_cycles+1;
    if(rd_rst_busy && rd_valid) fail("valid during read reset");
    if(rd_valid && rd_ready) begin
      if(expected_q.size()==0) fail("unexpected output transfer");
      expected=expected_q.pop_front();
      if(rd_data !== expected) fail($sformatf("data mismatch expected=%h actual=%h",expected,rd_data));
      read_count=read_count+1;
    end
  end
  task apply_reset;
    begin
      @(negedge wr_clk); wr_valid=0; rd_ready=0; rst=1;
      discarded=discarded+expected_q.size(); expected_q.delete();
      repeat(8) @(posedge wr_clk);
      @(negedge wr_clk); rst=0;
      wait(wr_rst_busy===0 && rd_rst_busy===0);
      repeat(8) @(posedge rd_clk);
      if(empty !== 1) fail("not empty after reset");
      reset_count=reset_count+1; active=1;
    end
  endtask
  task send_words(input integer count);
    integer i;
    begin
      for(i=0;i<count;i=i+1) begin
        @(negedge wr_clk); wr_valid=1;
        wr_data=(sequence_number*37+16'h1357) & 16'hffff;
        do @(posedge wr_clk); while(wr_ready !== 1'b1);
        sequence_number=sequence_number+1;
      end
      @(negedge wr_clk); wr_valid=0;
    end
  endtask
  task drain;
    begin
      @(negedge rd_clk); rd_ready=1;
      wait(expected_q.size()==0);
      repeat(20) @(posedge rd_clk);
      if(empty !== 1) fail("not empty after drain");
    end
  endtask
  initial begin
    // Allow power-up/GSR initialization to settle before the first user reset.
    #250; wait(wr_rst_busy===0 && rd_rst_busy===0);
    apply_reset();
    // Fill until true FULL, then release the reader and complete all writes.
    fork
      send_words(800);
      begin wait(full===1); repeat(20) @(negedge rd_clk); rd_ready=1; end
    join
    drain();
    // Continuous producer/consumer traffic.
    send_words(1500); drain();
    // Backpressure with alternating reader pauses during ongoing writes.
    fork
      send_words(900);
      begin repeat(45) begin
        repeat(15) @(negedge rd_clk); rd_ready=0;
        repeat(20) @(negedge rd_clk); rd_ready=1;
      end end
    join
    drain();
    // Reset while 100 accepted data words remain queued; both domains run.
    @(negedge rd_clk); rd_ready=0;
    send_words(100);
    if(expected_q.size()!=100) fail("reset scenario did not queue 100 words");
    apply_reset();
    @(negedge rd_clk); rd_ready=1;
    send_words(300); drain();
    if(written!=3600 || read_count!=3500 || discarded!=100 || expected_q.size()!=0) fail("accounting mismatch");
    if(reset_count!=2 || full_cycles==0 || empty_cycles==0 || paused_cycles==0 || max_pending<500) fail("coverage incomplete");
    fd=$fopen("fifo_result.txt","w");
    $fdisplay(fd,"PASS written=%0d read=%0d discarded=%0d pending=%0d resets=%0d full_cycles=%0d empty_cycles=%0d paused_cycles=%0d max_pending=%0d corrupt=%0d",written,read_count,discarded,expected_q.size(),reset_count,full_cycles,empty_cycles,paused_cycles,max_pending,CORRUPT);
    $fclose(fd); $display("FIFO_PASS written=%0d read=%0d discarded=%0d",written,read_count,discarded); $finish;
  end
  initial begin #2000000; fail("timeout"); end
endmodule
