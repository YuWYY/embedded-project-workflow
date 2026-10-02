# Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
set_dt_param -xsa [file normalize [lindex $argv 0]] -dir [file normalize [lindex $argv 1]] -board_dts zcu102-rev1.0
generate_sdt
exit
