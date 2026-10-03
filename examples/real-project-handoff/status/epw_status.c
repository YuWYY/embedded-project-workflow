/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#include "epw_status.h"
#include <stddef.h>
bool epw_status_init(epw_status *state, uint32_t now_ms, uint32_t period_ms)
{
    if (state == NULL || period_ms == 0u) return false;
    *state = (epw_status){0};
    state->last_tick = now_ms;
    state->last_publish = now_ms;
    state->period_ms = period_ms;
    return true;
}
bool epw_status_poll(epw_status *state, uint32_t now_ms)
{
    state->elapsed_ms += (uint32_t)(now_ms - state->last_tick);
    state->last_tick = now_ms;
    ++state->loops;
    if ((uint32_t)(now_ms - state->last_publish) < state->period_ms) return false;
    state->last_publish = now_ms;
    state->visible.seconds = (uint32_t)(state->elapsed_ms / 1000u);
    state->visible.loops = state->loops;
    return true;
}
