// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/settings_screen/SettingsPresenter.hpp>
#include <gui/settings_screen/SettingsView.hpp>
SettingsPresenter::SettingsPresenter(SettingsView& v) : view(v) {}
void SettingsPresenter::activate() { view.showState(model->paused()); }
void SettingsPresenter::stateChanged(uint32_t, bool paused) { view.showState(paused); }
void SettingsPresenter::togglePause() { model->togglePause(); }
