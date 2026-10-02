// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/dashboard_screen/DashboardPresenter.hpp>
#include <gui/dashboard_screen/DashboardView.hpp>
DashboardPresenter::DashboardPresenter(DashboardView& v) : view(v) {}
void DashboardPresenter::activate() { view.showState(model->value(), model->paused()); }
void DashboardPresenter::stateChanged(uint32_t value, bool paused) { view.showState(value, paused); }
