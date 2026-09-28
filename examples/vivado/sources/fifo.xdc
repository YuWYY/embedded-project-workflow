create_clock -period 12.500 -name wr_clk [get_ports wr_clk]
create_clock -period 10.000 -name rd_clk [get_ports rd_clk]
# Deliberately no blanket asynchronous clock-group exception here.
# Vivado loads the XPM implementation-specific CDC constraints during synthesis.
