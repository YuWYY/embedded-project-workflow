// Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_counter32;
reg clk=0, resetn=0;
reg [1:0] control=0;
wire [31:0] count;
integer checks=0;
integer result;
counter32 dut(.clk(clk), .resetn(resetn), .control(control), .count(count));
always #5 clk=~clk;
task step(input bit rst, input logic [1:0] ctrl, input logic [31:0] expected, input string contract);
begin
    @(negedge clk); resetn=rst; control=ctrl;
    @(posedge clk); #1;
    if(count !== expected) $fatal(1,"COUNTER_ASSERT %s expected=%h actual=%h resetn=%b control=%b",contract,expected,count,rst,ctrl);
    checks=checks+1;
end
endtask
initial begin
    step(0,2'b11,0,"RESET_PRIORITY");
    step(1,2'b00,0,"PAUSE_HOLD"); // default stopped
    step(1,2'b01,1,"ENABLE"); step(1,2'b01,2,"ENABLE"); step(1,2'b01,3,"ENABLE");
    step(1,2'b00,3,"PAUSE_HOLD"); step(1,2'b00,3,"PAUSE_HOLD");
    step(1,2'b11,0,"CLEAR_DOMINANCE");
    step(1,2'b01,1,"RESUME");
    step(1,2'b10,0,"CLEAR_WHILE_STOPPED");
    step(1,2'b00,0,"PAUSE_HOLD"); step(1,2'b01,1,"RESUME");
    step(0,2'b01,0,"RESET_RUNNING");
    step(1,2'b00,0,"PAUSE_HOLD");
    // Deposit a boundary value to test 32-bit modulo arithmetic without 2^32 cycles.
    @(negedge clk); dut.count=32'hfffffffe; resetn=1; control=1;
    @(posedge clk); #1;
    if(count !== 32'hffffffff) $fatal(1,"COUNTER_ASSERT pre-wrap");
    checks=checks+1;
    step(1,2'b01,0,"WRAP"); step(1,2'b01,1,"RESUME"); step(1,2'b00,1,"PAUSE_HOLD");
    result=$fopen("counter_result.txt","w");
    $fwrite(result,"PASS checks=%0d reset clear_priority pause resume wrap\n",checks);
    $fclose(result);
    $display("COUNTER_PASS checks=%0d",checks);
    $finish;
end
initial begin #5000; $fatal(1,"COUNTER_ASSERT timeout"); end
endmodule
