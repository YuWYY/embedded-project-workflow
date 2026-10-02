# Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
if {[version -short] ne "2025.1"} {error "Vivado 2025.1 required"}
set source_root [file normalize [lindex $argv 0]]
set output [file normalize [lindex $argv 1]]
create_project counter_sim [file join $output simulation] -part xczu9eg-ffvb1156-2-e
add_files [file join $source_root counter32.v]
add_files -fileset sim_1 [file join $source_root tb_counter32.sv]
set_property top tb_counter32 [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sim_1
launch_simulation -simset sim_1 -mode behavioral
close_sim
set log [file join $output simulation counter_sim.sim sim_1 behav xsim simulate.log]
set f [open $log r]; set text [read $f]; close $f
if {[regexp {(^|\n)(Error:|Fatal:|ERROR:)} $text] || ![string match "*COUNTER_PASS checks=18*" $text]} {error "Counter behavioral checks failed"}
file copy [file join $output simulation counter_sim.sim sim_1 behav xsim counter_result.txt] [file join $output counter_result.txt]
close_project
exit
