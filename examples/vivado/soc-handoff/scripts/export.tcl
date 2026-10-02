# Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
# Operates on the current BD. It never reapplies the preparation configuration.
set_param general.maxThreads 1
if {[version -short] ne "2025.1"} {error "Vivado 2025.1 required"}
set project [file normalize [lindex $argv 0]]
set output [file normalize [lindex $argv 1]]
open_project $project
set bd [get_files */system.bd]
if {[llength $bd] != 1} {error "Expected the current system.bd"}
open_bd_design $bd
validate_bd_design
save_bd_design
set f [open [file join $output bd_validated.txt] w]; puts $f "BD_VALIDATED"; close $f
generate_target all $bd
set wrappers [make_wrapper -files $bd -top]
add_files -norecurse $wrappers
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
# Disable cache only in this isolated project; fresh OOC/top runs remain observable.
config_ip_cache -disable_cache
reset_run synth_1
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%" || ![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {error "Top synthesis incomplete"}
open_run synth_1
report_utilization -file [file join $output utilization.rpt]
report_timing_summary -file [file join $output timing_synth.rpt]
report_clocks -file [file join $output clocks.rpt]
write_hw_platform -fixed -force -file [file join $output hardware.xsa]
set f [open [file join $output exported.txt] w]
puts $f "XSA_EXPORTED_WITHOUT_BITSTREAM synth_status=[get_property STATUS [get_runs synth_1]]"
close $f
close_project
exit
