// Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
// control[0]: enable, control[1]: synchronous clear. Reset has highest priority.
module counter32 (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 clk CLK" *)
    // ZCU102 board 3.4: requested 100 MHz; native PS result is 99,990,005 Hz.
    (* X_INTERFACE_PARAMETER = "ASSOCIATED_RESET resetn, FREQ_HZ 99990005" *)
    input wire clk,
    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 resetn RST" *)
    (* X_INTERFACE_PARAMETER = "POLARITY ACTIVE_LOW" *)
    input wire resetn,
    input wire [1:0] control,
    output reg [31:0] count
);
always @(posedge clk) begin
    if (!resetn) count <= 32'd0;
    else if (control[1]) count <= 32'd0;
    else if (control[0]) count <= count + 32'd1;
end
endmodule
