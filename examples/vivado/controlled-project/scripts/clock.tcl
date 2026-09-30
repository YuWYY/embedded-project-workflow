set_param general.maxThreads 4
set tool_version [version -short]
if {$tool_version ne "2025.1"} {error "This example is validated with Vivado 2025.1; found $tool_version"}
set vf [open tool_version.txt w]; puts $vf $tool_version; close $vf
set source_root [file normalize [lindex $argv 0]]
source [file normalize [file join $source_root .. config clock-config.tcl]]
if {![string is double -strict $output_mhz] || $output_mhz < 100 || $output_mhz > 125} {error "Output frequency outside agreed range"}
if {$input_mhz != 50} {error "Input clock must remain 50 MHz"}
set regenerate [expr {[llength $argv] > 1 && [lindex $argv 1] eq "regenerate"}]
if {$regenerate} {
  open_project ./p/c.xpr
  puts "PREVIOUS_REQUESTED_FREQ=[get_property CONFIG.CLKOUT1_REQUESTED_OUT_FREQ [get_ips clkgen]]"
  reset_target all [get_ips clkgen]
} else {
  create_project c ./p -part $test_part -force
  set_property target_language Verilog [current_project]
  create_ip -name clk_wiz -vendor xilinx.com -library ip -version 6.0 -module_name clkgen
}
# This isolated validation explicitly reruns OOC synthesis, including same-frequency
# regeneration. Disable cache only for the current project, never globally.
config_ip_cache -disable_cache
puts "PROJECT_IP_CACHE_PERMISSIONS=[get_property IP_CACHE_PERMISSIONS [current_project]]"
set_property -dict [list CONFIG.PRIM_IN_FREQ $input_mhz CONFIG.CLKOUT1_REQUESTED_OUT_FREQ $output_mhz CONFIG.USE_RESET {true} CONFIG.USE_LOCKED {true} CONFIG.RESET_TYPE {ACTIVE_HIGH}] [get_ips clkgen]
generate_target all [get_ips clkgen]
export_ip_user_files -of_objects [get_ips clkgen] -no_script -sync -force
set mf [open ip_properties.txt w]
foreach prop {IPDEF CONFIG.PRIM_IN_FREQ CONFIG.CLKOUT1_REQUESTED_OUT_FREQ CONFIG.MMCM_DIVCLK_DIVIDE CONFIG.MMCM_CLKFBOUT_MULT_F CONFIG.MMCM_CLKOUT0_DIVIDE_F CONFIG.USE_RESET CONFIG.USE_LOCKED} {
  puts $mf "$prop=[get_property $prop [get_ips clkgen]]"
}
close $mf
if {!$regenerate} {
  add_files $source_root/clock_top.sv
  add_files -fileset constrs_1 $source_root/clock.xdc
}
set_property top clock_top [get_filesets sources_1]
if {!$regenerate} {add_files -fileset sim_1 $source_root/tb_clock.sv}
set_property top tb_clock [get_filesets sim_1]
set_property generic "EXPECTED_NS=[expr {1000.0/$output_mhz}]" [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
launch_simulation -simset sim_1 -mode behavioral
close_sim
set lf [open ./p/c.sim/sim_1/behav/xsim/simulate.log r]; set simulation_log [read $lf]; close $lf
if {[regexp {(^|\n)(Error:|Fatal:|ERROR:)} $simulation_log]} {error "Simulation reported an error/fatal assertion"}
set results [glob -nocomplain ./p/c.sim/sim_1/behav/xsim/clock_result.txt]
if {[llength $results] != 1} {error "Clock simulation result missing"}
set sf [open [lindex $results 0] r]; set result [read $sf]; close $sf
puts "SIM_RESULT=$result"
if {![string match "PASS samples=400 resets=2*" $result]} {error "Clock simulation failed"}
# Regeneration invalidates IP output files; reset and build the OOC run
# explicitly rather than trusting the prior completed-run state.
if {[llength [get_runs -quiet clkgen_synth_1]] == 0} {create_ip_run [get_ips clkgen]}
if {$regenerate} {reset_runs clkgen_synth_1; reset_runs synth_1}
launch_runs clkgen_synth_1 -jobs 4
wait_on_run clkgen_synth_1
if {![string match "*Complete*" [get_property STATUS [get_runs clkgen_synth_1]]]} {error "IP synthesis incomplete"}
launch_runs synth_1 -jobs 4
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "Synthesis incomplete"}
if {![string match "*Complete*" [get_property STATUS [get_runs synth_1]]]} {error "Synthesis failed"}
open_run synth_1
report_utilization -file utilization.rpt
report_clocks -file clocks.rpt
report_timing_summary -file timing_synth.rpt
report_cdc -details -file cdc.rpt
check_timing -verbose -file check_timing.rpt
write_checkpoint -force synth.dcp
set f [open completed.txt w]; puts $f "CLOCK_COMPLETE mhz=$output_mhz synth_status=[get_property STATUS [get_runs synth_1]]"; close $f
close_project
exit
