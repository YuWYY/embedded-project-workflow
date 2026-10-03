/* Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT */
#include "epw_status.h"
#include <stdio.h>
#include <stdint.h>
#define CHECK(c, m) do { if (!(c)) { fprintf(stderr, "CONTRACT: %s\n", m); return 1; } } while (0)
int main(void)
{
    epw_status s;
    CHECK(!epw_status_init(&s, 0, 0), "zero period rejected");
    CHECK(epw_status_init(&s, 1500, 100), "init");
    CHECK(s.visible.seconds == 0 && s.visible.loops == 0, "initial snapshot");
    CHECK(!epw_status_poll(&s, 1599), "99ms no publish");
    CHECK(epw_status_poll(&s, 1600) && s.visible.loops == 2, "100ms publish");
    CHECK(epw_status_poll(&s, 4750), "late publish");
    CHECK(s.visible.seconds == 3 && s.visible.loops == 3, "real elapsed time, not refresh count");
    CHECK(!epw_status_poll(&s, 4750), "no catch-up refresh");
    CHECK(!epw_status_poll(&s, 4849), "late publish establishes next deadline");
    CHECK(epw_status_poll(&s, 4850), "next interval");
    CHECK(epw_status_init(&s, UINT32_MAX - 49u, 100), "wrap init");
    CHECK(!epw_status_poll(&s, 49), "tick wrap below deadline");
    CHECK(epw_status_poll(&s, 50), "tick wrap at deadline");
    CHECK(epw_status_poll(&s, 1950) && s.visible.seconds == 2, "elapsed across wrap");
    s.loops = UINT32_MAX;
    CHECK(epw_status_poll(&s, 2050) && s.visible.loops == 0, "unsigned loop wrap");
    CHECK(epw_status_init(&s, 0, 250), "250 init");
    CHECK(!epw_status_poll(&s, 100) && !epw_status_poll(&s, 249), "250 config honored");
    CHECK(epw_status_poll(&s, 250), "250 boundary");
    CHECK(epw_status_poll(&s, 3001) && s.visible.seconds == 3, "250 late elapsed");
    CHECK(epw_status_init(&s, 0, 100), "long uptime init");
    (void)epw_status_poll(&s, UINT32_C(0x80000000));
    (void)epw_status_poll(&s, UINT32_C(0xfffffff0));
    CHECK(epw_status_poll(&s, 127) && s.visible.seconds == 4294967u,
          "elapsed survives full tick period");
    puts("PASS status time, cadence, wrap and loop contracts");
    return 0;
}
