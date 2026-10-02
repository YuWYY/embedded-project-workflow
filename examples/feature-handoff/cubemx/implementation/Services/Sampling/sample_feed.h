/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#ifndef SAMPLE_FEED_H
#define SAMPLE_FEED_H

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t attempted;
    uint32_t sent;
    uint32_t failed;
    uint32_t missed_releases;
} SamplingSnapshot;

void SampleFeed_Entry(void *argument);
void Sampling_CheckCreated(void);
/* Task-context observation; counters wrap modulo 2^32. */
bool Sampling_Read(SamplingSnapshot *snapshot);

#ifdef __cplusplus
}
#endif
#endif
