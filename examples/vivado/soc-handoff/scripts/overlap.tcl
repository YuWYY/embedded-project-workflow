# Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
# Deliberately invalid extra peripheral, only in this disposable negative fixture.
set_param general.maxThreads 1
if {[version -short] ne "2025.1"} {error "Vivado 2025.1 required"}
open_project [file normalize [lindex $argv 0]]
open_bd_design [get_files */system.bd]
set_property CONFIG.NUM_MI {2} [get_bd_cells smartconnect_0]
set other [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 collision_gpio]
connect_bd_intf_net [get_bd_intf_pins smartconnect_0/M01_AXI] [get_bd_intf_pins $other/S_AXI]
connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] [get_bd_pins $other/s_axi_aclk]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins $other/s_axi_aresetn]
puts "NEGATIVE_OVERLAP_GPIO_READY"
set existing [get_bd_addr_segs -of_objects [get_bd_addr_spaces zynq_ultra_ps_e_0/Data] -filter {NAME =~ *axi_gpio_0*}]
if {[llength $existing] != 1} {error "Expected exactly one current original GPIO mapping"}
assign_bd_address -offset [get_property OFFSET $existing] -range [get_property RANGE $existing] -target_address_space [get_bd_addr_spaces zynq_ultra_ps_e_0/Data] [get_bd_addr_segs $other/S_AXI/Reg]
error "Native address assignment unexpectedly accepted overlap"
