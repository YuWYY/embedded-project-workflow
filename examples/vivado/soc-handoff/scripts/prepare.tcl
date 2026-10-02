# Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
# Original A baseline only. Never source this into a current user project.
set_param general.maxThreads 1
if {[version -short] ne "2025.1"} {error "Vivado 2025.1 required"}
set source_root [file normalize [lindex $argv 0]]
set output [file normalize [lindex $argv 1]]
if {[file exists [file join $output project soc_handoff.xpr]]} {error "New project required"}
create_project soc_handoff [file join $output project] -part xczu9eg-ffvb1156-2-e
set_property board_part xilinx.com:zcu102:part0:3.4 [current_project]
set_property target_language Verilog [current_project]
add_files [file join $source_root counter32.v]
create_bd_design system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:zynq_ultra_ps_e:3.5 zynq_ultra_ps_e_0]
apply_bd_automation -rule xilinx.com:bd_rule:zynq_ultra_ps_e -config {apply_board_preset "1"} $ps
set_property -dict [list CONFIG.PSU__USE__M_AXI_GP0 {1} CONFIG.PSU__USE__M_AXI_GP1 {0} CONFIG.PSU__USE__M_AXI_GP2 {0} CONFIG.PSU__MAXIGP0__DATA_WIDTH {32} CONFIG.PSU__FPGA_PL0_ENABLE {1} CONFIG.PSU__CRL_APB__PL0_REF_CTRL__FREQMHZ {100}] $ps
set sc [create_bd_cell -type ip -vlnv xilinx.com:ip:smartconnect:1.0 smartconnect_0]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {1}] $sc
set gpio [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 axi_gpio_0]
set_property -dict [list CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO_WIDTH {2} CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_DOUT_DEFAULT {0x00000000} CONFIG.C_GPIO2_WIDTH {32} CONFIG.C_ALL_INPUTS_2 {1} CONFIG.C_INTERRUPT_PRESENT {0}] $gpio
set rst [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 constant_one
set_property CONFIG.CONST_VAL {1} [get_bd_cells constant_one]
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:1.1 constant_zero
set_property CONFIG.CONST_VAL {0} [get_bd_cells constant_zero]
if {[catch {create_bd_cell -type module -reference counter32 counter32_0} e options]} {
    puts "MODULE_REFERENCE_ERROR=$e"
    puts "MODULE_REFERENCE_OPTIONS=$options"
    return -options $options $e
}
connect_bd_intf_net [get_bd_intf_pins $ps/M_AXI_HPM0_FPD] [get_bd_intf_pins $sc/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins $sc/M00_AXI] [get_bd_intf_pins $gpio/S_AXI]
connect_bd_net [get_bd_pins $ps/pl_clk0] [get_bd_pins $ps/maxihpm0_fpd_aclk] [get_bd_pins $sc/aclk] [get_bd_pins $gpio/s_axi_aclk] [get_bd_pins $rst/slowest_sync_clk] [get_bd_pins counter32_0/clk]
connect_bd_net [get_bd_pins $ps/pl_resetn0] [get_bd_pins $rst/ext_reset_in]
connect_bd_net [get_bd_pins constant_one/dout] [get_bd_pins $rst/dcm_locked]
connect_bd_net [get_bd_pins constant_zero/dout] [get_bd_pins $rst/aux_reset_in] [get_bd_pins $rst/mb_debug_sys_rst]
connect_bd_net [get_bd_pins $rst/peripheral_aresetn] [get_bd_pins $sc/aresetn] [get_bd_pins $gpio/s_axi_aresetn] [get_bd_pins counter32_0/resetn]
connect_bd_net [get_bd_pins $gpio/gpio_io_o] [get_bd_pins counter32_0/control]
connect_bd_net [get_bd_pins counter32_0/count] [get_bd_pins $gpio/gpio2_io_i]
assign_bd_address -offset 0xA0000000 -range 0x00010000 -target_address_space [get_bd_addr_spaces $ps/Data] [get_bd_addr_segs $gpio/S_AXI/Reg] -force
save_bd_design
validate_bd_design
save_bd_design
set f [open [file join $output prepared.txt] w]; puts $f "PREPARED_A base=0xA0000000 range=0x10000"; close $f
close_project
exit
