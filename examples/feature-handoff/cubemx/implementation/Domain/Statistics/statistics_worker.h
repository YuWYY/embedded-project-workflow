/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#ifndef STATISTICS_WORKER_H
#define STATISTICS_WORKER_H

#include "epw_stats.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    epw_stats_result window;
    uint32_t received;
    uint32_t receive_errors;
} StatisticsSnapshot;

void StatsWorker_Entry(void *argument);
/* Task-context snapshot. False until the first successful receive.
 * A non-NULL output is still written when false. Counters wrap modulo 2^32.
 */
bool Statistics_Read(StatisticsSnapshot *snapshot);

#ifdef __cplusplus
}
#endif
#endif
