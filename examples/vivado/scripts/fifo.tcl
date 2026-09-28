set_param general.maxThreads 4
set tool_version [version -short]
if {$tool_version ne "2025.1"} {error "This example is validated with Vivado 2025.1; found $tool_version"}
set vf [open tool_version.txt w]; puts $vf $tool_version; close $vf
set source_root [file normalize [lindex $argv 0]]
set corrupt [lindex $argv 1]
if {$corrupt ni {0 1}} {error "Invalid negative-control setting"}
create_project f ./p -part xc7a200tfbg484-2 -force
set_property target_language Verilog [current_project]
set_property XPM_LIBRARIES {XPM_CDC XPM_MEMORY XPM_FIFO} [current_project]
add_files $source_root/fifo_top.sv
add_files -fileset constrs_1 $source_root/fifo.xdc
set_property top fifo_top [get_filesets sources_1]
add_files -fileset sim_1 $source_root/tb_fifo.sv
set_property top tb_fifo [get_filesets sim_1]
set_property generic "CORRUPT=$corrupt" [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
update_compile_order -fileset sources_1
update_compile_order -fileset sim_1
launch_simulation -simset sim_1 -mode behavioral
close_sim
set lf [open ./p/f.sim/sim_1/behav/xsim/simulate.log r]; set simulation_log [read $lf]; close $lf
if {[regexp {(^|\n)(Error:|ERROR:)} $simulation_log]} {error "Simulation reported an error assertion"}
if {[regexp {(^|\n)Fatal:} $simulation_log] && !$corrupt} {error "Simulation reported fatal assertion"}
set results [glob -nocomplain ./p/f.sim/sim_1/behav/xsim/fifo_result.txt]
if {[llength $results] != 1} {error "FIFO simulation result missing"}
set sf [open [lindex $results 0] r]; set result [read $sf]; close $sf
puts "SIM_RESULT=$result"
if {$corrupt} {
  if {![string match "FAIL reason=data mismatch*corrupt=1*" $result]} {error "Negative control did not detect the controlled mismatch"}
  set f [open completed.txt w]; puts $f "NEGATIVE_CONTROL_DETECTED $result"; close $f
  close_project
  exit
}
if {![string match "PASS written=3600 read=3500 discarded=100 pending=0 resets=2*corrupt=0*" $result]} {error "FIFO simulation failed"}
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
report_exceptions -file exceptions.rpt
report_bus_skew -file bus_skew_synth.rpt
write_xdc -force effective_constraints.xdc
write_checkpoint -force synth.dcp
set f [open completed.txt w]; puts $f "FIFO_COMPLETE synth_status=[get_property STATUS [get_runs synth_1]]"; close $f
close_project
exit
