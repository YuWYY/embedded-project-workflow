`timescale 1ns/1ps
module fifo_top #(parameter integer CORRUPT=0)(
  input wire wr_clk, rd_clk, rst,
  input wire [15:0] wr_data, input wire wr_valid, output wire wr_ready,
  output wire [15:0] rd_data, output wire rd_valid, input wire rd_ready,
  output wire full, empty, wr_rst_busy, rd_rst_busy);
  wire [15:0] raw_data;
  assign wr_ready = !rst && !wr_rst_busy && !full;
  assign rd_valid = !rst && !rd_rst_busy && !empty;
  assign rd_data = raw_data ^ (CORRUPT ? 16'h0001 : 16'h0000);
  xpm_fifo_async #(
    .FIFO_MEMORY_TYPE("block"), .ECC_MODE("no_ecc"),
    .FIFO_WRITE_DEPTH(512), .WRITE_DATA_WIDTH(16), .READ_DATA_WIDTH(16),
    .WR_DATA_COUNT_WIDTH(10), .RD_DATA_COUNT_WIDTH(10),
    .READ_MODE("fwft"), .FIFO_READ_LATENCY(0),
    .CDC_SYNC_STAGES(2), .RELATED_CLOCKS(0),
    .USE_ADV_FEATURES("0707"), .SIM_ASSERT_CHK(1), .EN_SIM_ASSERT_ERR("error")
  ) u_fifo (
    .rst(rst), .wr_clk(wr_clk), .rd_clk(rd_clk),
    .din(wr_data), .wr_en(wr_valid && wr_ready),
    .dout(raw_data), .rd_en(rd_ready && rd_valid),
    .full(full), .empty(empty), .wr_rst_busy(wr_rst_busy), .rd_rst_busy(rd_rst_busy),
    .sleep(1'b0), .injectsbiterr(1'b0), .injectdbiterr(1'b0),
    .prog_full(), .wr_data_count(), .overflow(), .almost_full(), .wr_ack(),
    .prog_empty(), .rd_data_count(), .underflow(), .almost_empty(), .data_valid(), .sbiterr(), .dbiterr()
  );
endmodule
