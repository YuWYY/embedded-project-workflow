// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#ifndef SETTINGSVIEW_HPP
#define SETTINGSVIEW_HPP
#include <gui_generated/settings_screen/SettingsViewBase.hpp>
class SettingsView : public SettingsViewBase {
public:
    SettingsView() {}
    virtual ~SettingsView() {}
    virtual void setupScreen() { SettingsViewBase::setupScreen(); }
    virtual void tearDownScreen() { SettingsViewBase::tearDownScreen(); }
    virtual void togglePause();
    void showState(bool paused);
};
#endif
