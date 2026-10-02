# SPDX-License-Identifier: MIT
# Copyright (c) 2026 YuWYY
get_filename_component(EPW_STATS_COMMON_DIR
    "${CMAKE_CURRENT_LIST_DIR}/../../../common/rolling-stats" ABSOLUTE)

idf_component_register(SRCS "${EPW_STATS_COMMON_DIR}/epw_stats.c"
                       INCLUDE_DIRS "${EPW_STATS_COMMON_DIR}")
