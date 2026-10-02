# Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
# Dedicated negative fixture only; never point this at a maintained user project.
set_param general.maxThreads 1
if {[version -short] ne "2025.1"} {error "Vivado 2025.1 required"}
open_project [file normalize [lindex $argv 0]]
open_bd_design [get_files */system.bd]
set assigned [get_bd_addr_segs -of_objects [get_bd_addr_spaces zynq_ultra_ps_e_0/Data] -filter {NAME =~ *axi_gpio_0*}]
if {[llength $assigned] != 1} {error "Negative setup requires exactly one GPIO assignment"}
delete_bd_objs $assigned
save_bd_design
puts "NEGATIVE_UNASSIGNED_GPIO_READY"
validate_bd_design -force
error "Native validate unexpectedly accepted unassigned GPIO"
