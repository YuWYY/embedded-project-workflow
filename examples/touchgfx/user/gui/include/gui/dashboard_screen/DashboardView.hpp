// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#ifndef DASHBOARDVIEW_HPP
#define DASHBOARDVIEW_HPP
#include <gui_generated/dashboard_screen/DashboardViewBase.hpp>
class DashboardView : public DashboardViewBase {
public:
    DashboardView() {}
    virtual ~DashboardView() {}
    virtual void setupScreen() { DashboardViewBase::setupScreen(); }
    virtual void tearDownScreen() { DashboardViewBase::tearDownScreen(); }
    void showState(uint32_t value, bool paused);
};
#endif
