// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/controls_screen/ControlsView.hpp>
#include <touchgfx/Unicode.hpp>
void ControlsView::togglePause() { presenter->togglePause(); }
void ControlsView::showState(bool paused) {
    touchgfx::Unicode::snprintf(pausedValueBuffer, PAUSEDVALUE_SIZE, "%u", paused ? 1U : 0U);
    pausedValue.invalidate();
}
