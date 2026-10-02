// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/controls_screen/ControlsPresenter.hpp>
#include <gui/controls_screen/ControlsView.hpp>
ControlsPresenter::ControlsPresenter(ControlsView& v) : view(v) {}
void ControlsPresenter::activate() { view.showState(model->paused()); }
void ControlsPresenter::stateChanged(uint32_t, bool paused) { view.showState(paused); }
void ControlsPresenter::togglePause() { model->togglePause(); }
