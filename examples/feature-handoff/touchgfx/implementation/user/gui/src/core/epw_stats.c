/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#include "epw_stats.h"
#include <stddef.h>

static bool epw_stats_valid(const epw_stats *state)
{
    return state != NULL && state->storage != NULL &&
           state->capacity >= 1U && state->capacity <= EPW_STATS_MAX_CAPACITY &&
           state->count <= state->capacity && state->next < state->capacity;
}

bool epw_stats_init(epw_stats *state, uint32_t *storage, uint32_t capacity)
{
    if (state == NULL) {
        return false;
    }
    state->storage = NULL;
    state->capacity = 0U;
    state->count = 0U;
    state->next = 0U;
    state->sum = 0U;
    if (storage == NULL || capacity == 0U || capacity > EPW_STATS_MAX_CAPACITY) {
        return false;
    }
    state->storage = storage;
    state->capacity = capacity;
    return true;
}

bool epw_stats_push(epw_stats *state, uint32_t sample)
{
    if (!epw_stats_valid(state)) {
        return false;
    }
    if (state->count == state->capacity) {
        state->sum -= state->storage[state->next];
    } else {
        ++state->count;
    }
    state->storage[state->next] = sample;
    state->sum += sample;
    state->next = (state->next + 1U) % state->capacity;
    return true;
}

void epw_stats_reset(epw_stats *state)
{
    if (state != NULL) {
        state->count = 0U;
        state->next = 0U;
        state->sum = 0U;
    }
}

bool epw_stats_read(const epw_stats *state, epw_stats_result *result)
{
    uint32_t i;
    uint32_t minimum;
    uint32_t maximum;
    if (result == NULL) {
        return false;
    }
    result->count = 0U;
    result->minimum = 0U;
    result->maximum = 0U;
    result->mean = 0U;
    if (!epw_stats_valid(state) || state->count == 0U) {
        return false;
    }
    minimum = state->storage[0];
    maximum = minimum;
    for (i = 1U; i < state->count; ++i) {
        if (state->storage[i] < minimum) {
            minimum = state->storage[i];
        }
        if (state->storage[i] > maximum) {
            maximum = state->storage[i];
        }
    }
    result->count = state->count;
    result->minimum = minimum;
    result->maximum = maximum;
    result->mean = (uint32_t)(state->sum / state->count);
    return true;
}
