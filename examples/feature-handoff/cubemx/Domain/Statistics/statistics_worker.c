/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#include "statistics_worker.h"
#include "cmsis_os2.h"

/* Baseline only: the feature agent will implement the queue consumer. */
void StatsWorker_Entry(void *argument)
{
  (void)argument;
  for (;;) {
    osDelay(1U);
  }
}
