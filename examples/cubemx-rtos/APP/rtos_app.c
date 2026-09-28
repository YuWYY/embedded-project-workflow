/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#include "rtos_app.h"
#include "cmsis_os2.h"
#include "main.h"

extern osThreadId_t ProducerHandle;
extern osThreadId_t ConsumerHandle;
extern osMessageQueueId_t SamplesHandle;

/* Observability only: no board pin, power-stage or communication operation. */
volatile uint32_t rtos_app_sent;
volatile uint32_t rtos_app_received;
volatile uint32_t rtos_app_sequence_errors;

void RtosApp_CheckCreated(void)
{
  if (ProducerHandle == NULL || ConsumerHandle == NULL || SamplesHandle == NULL)
    Error_Handler();
}

void Producer_Entry(void *argument)
{
  uint32_t value = 0U;
  (void)argument;
  for (;;) {
    if (osMessageQueuePut(SamplesHandle, &value, 0U, osWaitForever) != osOK)
      Error_Handler();
    ++value;
    rtos_app_sent = value;
    osDelay(1U);
  }
}

#ifndef RTOS_TEST_OMIT_CONSUMER
void Consumer_Entry(void *argument)
{
  uint32_t expected = 0U;
  uint32_t value;
  (void)argument;
  for (;;) {
    if (osMessageQueueGet(SamplesHandle, &value, NULL, osWaitForever) != osOK)
      Error_Handler();
    if (value != expected) {
      ++rtos_app_sequence_errors;
      Error_Handler();
    }
    ++expected;
    rtos_app_received = expected;
  }
}
#endif
