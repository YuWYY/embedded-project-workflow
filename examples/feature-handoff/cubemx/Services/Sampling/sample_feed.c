/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#include "sample_feed.h"
#include "cmsis_os2.h"
#include "main.h"

extern osThreadId_t SampleFeedHandle;
extern osThreadId_t StatsWorkerHandle;
extern osMessageQueueId_t SampleQueueHandle;

void Sampling_CheckCreated(void)
{
  if (SampleFeedHandle == NULL || StatsWorkerHandle == NULL || SampleQueueHandle == NULL)
    Error_Handler();
}

/* Baseline only: the feature agent will implement the sample producer. */
void SampleFeed_Entry(void *argument)
{
  (void)argument;
  for (;;) {
    osDelay(1U);
  }
}
