/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#ifndef EPW_STATUS_H
#define EPW_STATUS_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {
    uint32_t seconds;
    uint32_t loops;
} epw_status_snapshot;
typedef struct {
    uint64_t elapsed_ms;
    uint32_t last_tick;
    uint32_t last_publish;
    uint32_t loops;
    uint32_t period_ms;
    epw_status_snapshot visible;
} epw_status;
/* Call before entering the main loop. A zero period is rejected. */
bool epw_status_init(epw_status *state, uint32_t now_ms, uint32_t period_ms);
/* Call once per main-loop iteration, even while another page is shown.
 * Unsigned tick subtraction requires less than one complete tick wrap between
 * calls. Late calls publish once; UI rendering remains independently scheduled.
 * Published seconds wrap after UINT32_MAX seconds, loops after UINT32_MAX calls.
 */
bool epw_status_poll(epw_status *state, uint32_t now_ms);
#endif
