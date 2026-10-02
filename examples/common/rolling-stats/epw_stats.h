/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#ifndef EPW_STATS_H
#define EPW_STATS_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define EPW_STATS_MAX_CAPACITY 16U

/* Caller owns this state and its storage. Fields are private to the API.
 * Storage must remain alive and must not overlap the state or output result.
 * A host sharing a window between execution contexts must provide locking.
 */
typedef struct {
    uint32_t *storage;
    uint32_t capacity;
    uint32_t count;
    uint32_t next;
    uint64_t sum;
} epw_stats;

typedef struct {
    uint32_t count;
    uint32_t minimum;
    uint32_t maximum;
    uint32_t mean;
} epw_stats_result;

/* Invalid init leaves a non-NULL state empty and unusable until valid init. */
bool epw_stats_init(epw_stats *state, uint32_t *storage, uint32_t capacity);
bool epw_stats_push(epw_stats *state, uint32_t sample);
/* Reset keeps a valid state's caller storage and capacity for reuse. */
void epw_stats_reset(epw_stats *state);
/* Empty/invalid state returns false, zeroing a non-NULL result. */
bool epw_stats_read(const epw_stats *state, epw_stats_result *result);

#ifdef __cplusplus
}
#endif

#endif
