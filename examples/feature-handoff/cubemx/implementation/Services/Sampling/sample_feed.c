/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#include "sample_feed.h"
#include "cmsis_os2.h"
#include "FreeRTOS.h"
#include "task.h"
#include "main.h"

#define SAMPLE_PERIOD_TICKS 10U

extern osThreadId_t SampleFeedHandle;
extern osThreadId_t StatsWorkerHandle;
extern osMessageQueueId_t SampleQueueHandle;

static SamplingSnapshot sampling_snapshot;

void Sampling_CheckCreated(void)
{
    if (SampleFeedHandle == NULL || StatsWorkerHandle == NULL || SampleQueueHandle == NULL) {
        Error_Handler();
    }
}

bool Sampling_Read(SamplingSnapshot *snapshot)
{
    if (snapshot == NULL) {
        return false;
    }
    taskENTER_CRITICAL();
    *snapshot = sampling_snapshot;
    taskEXIT_CRITICAL();
    return true;
}

void SampleFeed_Entry(void *argument)
{
    uint32_t sample = 10U;
    uint32_t next_tick = osKernelGetTickCount();
    osStatus_t status;
    (void)argument;

    for (;;) {
        next_tick += SAMPLE_PERIOD_TICKS;
        if (osDelayUntil(next_tick) != osOK) {
            /* A missed deadline starts a new cadence, avoiding catch-up bursts. */
            next_tick = osKernelGetTickCount();
            taskENTER_CRITICAL();
            ++sampling_snapshot.missed_releases;
            taskEXIT_CRITICAL();
            continue;
        }
        status = osMessageQueuePut(SampleQueueHandle, &sample, 0U, 0U);
        taskENTER_CRITICAL();
        ++sampling_snapshot.attempted;
        if (status == osOK) {
            ++sampling_snapshot.sent;
        } else {
            ++sampling_snapshot.failed;
        }
        taskEXIT_CRITICAL();
        /* Advance after every attempted send, including a full-queue drop. */
        sample = sample == 90U ? 10U : sample + 10U;
    }
}
