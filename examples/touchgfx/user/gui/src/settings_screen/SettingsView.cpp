// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/settings_screen/SettingsView.hpp>
#include <touchgfx/Unicode.hpp>
void SettingsView::togglePause() { presenter->togglePause(); }
void SettingsView::showState(bool paused) {
    touchgfx::Unicode::snprintf(pausedValueBuffer, PAUSEDVALUE_SIZE, "%u", paused ? 1U : 0U);
    pausedValue.invalidate();
}
