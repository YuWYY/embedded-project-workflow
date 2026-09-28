// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/dashboard_screen/DashboardView.hpp>
#include <touchgfx/Unicode.hpp>
void DashboardView::showState(uint32_t value, bool paused) {
    touchgfx::Unicode::snprintf(sampleValueBuffer, SAMPLEVALUE_SIZE, "%u", static_cast<unsigned>(value));
    touchgfx::Unicode::snprintf(pausedValueBuffer, PAUSEDVALUE_SIZE, "%u", paused ? 1U : 0U);
    sampleValue.invalidate();
    pausedValue.invalidate();
}
