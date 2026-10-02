/* SPDX-License-Identifier: MIT
 * Copyright (c) 2026 YuWYY
 */
#include <inttypes.h>
#include <stdint.h>

#include "sdkconfig.h"
#include "esp_log.h"
#include "epw_stats.h"

_Static_assert(CONFIG_EPW_STATS_WINDOW >= 1 && CONFIG_EPW_STATS_WINDOW <= 16,
               "EPW statistics window must be in the supported range");

void app_main(void)
{
    static const char *const tag = "epw_stats";
    uint32_t storage[CONFIG_EPW_STATS_WINDOW];
    epw_stats stats;
    epw_stats_result result;

    if (!epw_stats_init(&stats, storage, CONFIG_EPW_STATS_WINDOW)) {
        ESP_LOGE(tag, "statistics initialization failed");
        return;
    }

    /* One synthetic batch in the existing IDF main task. */
    for (uint32_t sample = 10; sample <= 90; sample += 10) {
        if (!epw_stats_push(&stats, sample)) {
            ESP_LOGE(tag, "sample insertion failed");
            return;
        }
    }

    if (!epw_stats_read(&stats, &result)) {
        ESP_LOGE(tag, "statistics result is empty or invalid");
        return;
    }

    ESP_LOGI(tag, "window=%d count=%" PRIu32 " min=%" PRIu32
             " max=%" PRIu32 " mean=%" PRIu32,
             CONFIG_EPW_STATS_WINDOW, result.count, result.minimum,
             result.maximum, result.mean);
}
