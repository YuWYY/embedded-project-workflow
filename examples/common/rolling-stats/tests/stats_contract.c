/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 YuWYY
 * Independent expected outcomes; this is not the rolling implementation. */
#include "epw_stats.h"
#include <stdint.h>
#include <stdio.h>

#define CHECK(c) do { if (!(c)) { fprintf(stderr, "contract failure at line %d: %s\n", __LINE__, #c); return 1; } } while (0)

static int expect(epw_stats *state, uint32_t count, uint32_t lo, uint32_t hi, uint32_t mean)
{
    epw_stats_result value;
    CHECK(epw_stats_read(state, &value));
    CHECK(value.count == count);
    CHECK(value.minimum == lo);
    CHECK(value.maximum == hi);
    CHECK(value.mean == mean);
    return 0;
}

int main(void)
{
    epw_stats state;
    epw_stats_result empty;
    uint32_t storage[16];
    uint32_t i;
    CHECK(!epw_stats_init(&state, storage, 0));
    CHECK(!epw_stats_init(&state, storage, 17));
    CHECK(epw_stats_init(&state, storage, 8));
    CHECK(!epw_stats_read(&state, &empty));
    CHECK(empty.count == 0 && empty.minimum == 0 && empty.maximum == 0 && empty.mean == 0);
    CHECK(epw_stats_push(&state, 10));
    CHECK(expect(&state, 1, 10, 10, 10) == 0);
    for (i=20; i<=80; i+=10) CHECK(epw_stats_push(&state, i));
    CHECK(expect(&state, 8, 10, 80, 45) == 0);
    CHECK(epw_stats_push(&state, 90));
    CHECK(expect(&state, 8, 20, 90, 55) == 0);
    epw_stats_reset(&state);
    CHECK(!epw_stats_read(&state, &empty));
    CHECK(empty.count == 0);
    CHECK(epw_stats_push(&state, 123));
    CHECK(expect(&state, 1, 123, 123, 123) == 0);

    CHECK(epw_stats_init(&state, storage, 3));
    CHECK(epw_stats_push(&state, 9));
    CHECK(epw_stats_push(&state, 1));
    CHECK(epw_stats_push(&state, 4));
    CHECK(expect(&state, 3, 1, 9, 4) == 0);
    CHECK(epw_stats_push(&state, 2));
    CHECK(expect(&state, 3, 1, 4, 2) == 0);
    CHECK(epw_stats_push(&state, 8));
    CHECK(expect(&state, 3, 2, 8, 4) == 0);

    CHECK(epw_stats_init(&state, storage, 1));
    CHECK(epw_stats_push(&state, UINT32_MAX));
    CHECK(expect(&state, 1, UINT32_MAX, UINT32_MAX, UINT32_MAX) == 0);
    CHECK(epw_stats_push(&state, 0));
    CHECK(expect(&state, 1, 0, 0, 0) == 0);

    CHECK(epw_stats_init(&state, storage, 16));
    for(i=0; i<16; ++i) CHECK(epw_stats_push(&state, UINT32_MAX));
    CHECK(expect(&state, 16, UINT32_MAX, UINT32_MAX, UINT32_MAX) == 0);
    CHECK(epw_stats_push(&state, 0));
    CHECK(expect(&state, 16, 0, UINT32_MAX, 4026531839UL) == 0);
    puts("stats contract PASS");
    return 0;
}
