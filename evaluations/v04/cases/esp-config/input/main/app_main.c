/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 YuWYY
 * Original scenario input; no SDK-generated content.
 */
#include <stdint.h>

volatile uint32_t app_heartbeat;

void app_main(void)
{
    ++app_heartbeat;
}
