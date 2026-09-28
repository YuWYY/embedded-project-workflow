`timescale 1ns/1ps
module clock_top(input wire clk_in, input wire reset, output wire clk_out, output wire reset_out, output wire locked);
  clkgen u_clk (.clk_in1(clk_in), .reset(reset), .clk_out1(clk_out), .locked(locked));
  // User owned asynchronous assertion / synchronous release in generated domain.
  (* ASYNC_REG = "TRUE" *) reg [2:0] reset_pipe = 3'b111;
  wire reset_request = reset | ~locked;
  always @(posedge clk_out or posedge reset_request)
    if (reset_request) reset_pipe <= 3'b111;
    else reset_pipe <= {reset_pipe[1:0], 1'b0};
  assign reset_out = reset_pipe[2];
endmodule
