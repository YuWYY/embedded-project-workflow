`timescale 1ns/1ps
module tb_clock;
  parameter real EXPECTED_NS = 10.0;
  reg clk_in=0, reset=1;
  wire clk_out, reset_out, locked;
  integer samples=0, resets=0, fd, errors=0;
  real before_edge, measured;
  always #10 clk_in=~clk_in;
  clock_top dut(.*);
  task fail(input string why);
    begin
      fd=$fopen("clock_result.txt","w");
      $fdisplay(fd,"FAIL reason=%s samples=%0d resets=%0d",why,samples,resets);
      $fclose(fd); $fatal(1,"CLOCK_FAIL %s",why);
    end
  endtask
  task check_lock_and_release;
    integer edges;
    begin
      wait(locked === 1'b1);
      edges=0;
      while(reset_out === 1'b1 && edges<8) begin
        @(posedge clk_out); #0.001; edges=edges+1;
      end
      if(reset_out !== 0 || edges<2 || edges>4) fail("reset release sequence");
      @(posedge clk_out); before_edge=$realtime;
      repeat(200) begin
        @(posedge clk_out); measured=$realtime-before_edge; before_edge=$realtime;
        if(measured < EXPECTED_NS-0.02 || measured > EXPECTED_NS+0.02) fail("output period");
        if(reset_out !== 0 || locked !== 1) fail("unstable lock or reset");
        samples=samples+1;
      end
      resets=resets+1;
    end
  endtask
  initial begin
    #200; reset=0;
    check_lock_and_release();
    #3; reset=1; #0.001;
    if(reset_out !== 1) fail("reset did not assert asynchronously");
    #200; reset=0;
    check_lock_and_release();
    if(samples != 400 || resets != 2) fail("missing coverage");
    fd=$fopen("clock_result.txt","w");
    $fdisplay(fd,"PASS samples=%0d resets=%0d expected_ns=%0.3f",samples,resets,EXPECTED_NS);
    $fclose(fd); $display("CLOCK_PASS samples=%0d resets=%0d",samples,resets); $finish;
  end
  initial begin #1000000; fail("timeout"); end
endmodule
