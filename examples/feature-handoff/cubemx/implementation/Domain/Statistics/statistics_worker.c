/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#include "statistics_worker.h"
#include "cmsis_os2.h"
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"

#define STATISTICS_WINDOW_CAPACITY 8U

extern osMessageQueueId_t SampleQueueHandle;

static epw_stats statistics_window;
static uint32_t statistics_storage[STATISTICS_WINDOW_CAPACITY];
static StatisticsSnapshot statistics_snapshot;

bool Statistics_Read(StatisticsSnapshot *snapshot)
{
    if (snapshot == NULL) {
        return false;
    }
    taskENTER_CRITICAL();
    *snapshot = statistics_snapshot;
    taskEXIT_CRITICAL();
    return snapshot->window.count != 0U;
}

void StatsWorker_Entry(void *argument)
{
    uint32_t sample;
    epw_stats_result result;
    (void)argument;

    if (!epw_stats_init(&statistics_window, statistics_storage, STATISTICS_WINDOW_CAPACITY)) {
        Error_Handler();
        return;
    }
    for (;;) {
        if (osMessageQueueGet(SampleQueueHandle, &sample, NULL, osWaitForever) == osOK) {
            if (!epw_stats_push(&statistics_window, sample) ||
                !epw_stats_read(&statistics_window, &result)) {
                Error_Handler();
                return;
            }
            taskENTER_CRITICAL();
            statistics_snapshot.window = result;
            ++statistics_snapshot.received;
            taskEXIT_CRITICAL();
        } else {
            taskENTER_CRITICAL();
            ++statistics_snapshot.receive_errors;
            taskEXIT_CRITICAL();
            /* Unexpected queue errors must not turn this task into a busy loop. */
            osDelay(1U);
        }
    }
}
