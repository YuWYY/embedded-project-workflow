// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#ifndef SETTINGSVIEW_HPP
#define SETTINGSVIEW_HPP
#include <gui_generated/controls_screen/ControlsViewBase.hpp>
class ControlsView : public ControlsViewBase {
public:
    ControlsView() {}
    virtual ~ControlsView() {}
    virtual void setupScreen() { ControlsViewBase::setupScreen(); }
    virtual void tearDownScreen() { ControlsViewBase::tearDownScreen(); }
    virtual void togglePause();
    void showState(bool paused);
};
#endif
