# Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
# Recreate the narrow original case from saved native inputs, never prepare.tcl.
set_param general.maxThreads 1
if {[version -short] ne "2025.1"} {error "Vivado 2025.1 required"}
if {[llength $argv] < 5} {error "Expected output, part, board, top and separate BD names; got [llength $argv]"}
lassign $argv output part board top
set bd_names [lrange $argv 4 end]
set output [file normalize $output]
if {[file exists [file join $output project]]} {error "Project destination must not exist"}
create_project soc_handoff [file join $output project] -part $part
set_property board_part $board [current_project]
set_property default_lib xil_defaultlib [current_project]
config_ip_cache -disable_cache
add_files -norecurse [file join $output sources counter32.v]
foreach bd_name $bd_names {
    import_files -norecurse [file join $output input_bd $bd_name ${bd_name}.bd]
}
set bd [get_files */system.bd]
if {[llength $bd] != 1} {error "Expected one imported system.bd"}
open_bd_design $bd
validate_bd_design
save_bd_design
# The tool manages this wrapper; the independent original counter is preserved.
generate_target all $bd
set wrappers [make_wrapper -files $bd -top]
add_files -norecurse $wrappers
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
set f [open [file join $output imported_sources.txt] w]
puts $f "part=[get_property PART [current_project]]"
puts $f "board_part=[get_property BOARD_PART [current_project]]"
puts $f "top=[get_property TOP [current_fileset]]"
foreach src [get_files -of_objects [get_filesets sources_1]] {
    puts $f "source=$src"
}
puts $f "synthesis_compile_order:"
foreach src [get_files -compile_order sources -used_in synthesis] {puts $f $src}
close $f
close_project
exit
