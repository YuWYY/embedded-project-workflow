/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#include "telemetry_tasks.h"
#include "cmsis_os2.h"
#include "main.h"

extern osThreadId_t LoggerHandle;
extern osThreadId_t SamplerHandle;
extern osMessageQueueId_t FramesHandle;
volatile uint32_t telemetry_logged;
volatile uint32_t telemetry_sampled;
volatile uint32_t telemetry_order_errors;

void Telemetry_CheckCreated(void)
{
  if (LoggerHandle == NULL || SamplerHandle == NULL || FramesHandle == NULL)
    Error_Handler();
}

/* First configured task is the consumer and is dynamically allocated. */
void Logger_Entry(void *argument)
{
  uint32_t expected = 0U;
  uint32_t frame;
  (void)argument;
  for (;;) {
    if (osMessageQueueGet(FramesHandle, &frame, NULL, osWaitForever) != osOK)
      Error_Handler();
    if (frame != expected) {
      ++telemetry_order_errors;
      Error_Handler();
    }
    telemetry_logged = ++expected;
  }
}

void Sampler_Entry(void *argument)
{
  uint32_t sequence = 0U;
  (void)argument;
  for (;;) {
    if (osMessageQueuePut(FramesHandle, &sequence, 0U, osWaitForever) != osOK)
      Error_Handler();
    telemetry_sampled = ++sequence;
    osDelay(2U);
  }
}
