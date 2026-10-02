// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#ifndef DASHBOARDPRESENTER_HPP
#define DASHBOARDPRESENTER_HPP
#include <gui/model/ModelListener.hpp>
#include <mvp/Presenter.hpp>
class DashboardView;
class DashboardPresenter : public touchgfx::Presenter, public ModelListener {
public:
    explicit DashboardPresenter(DashboardView& v);
    virtual ~DashboardPresenter() {}
    virtual void activate();
    virtual void deactivate() {}
    virtual void stateChanged(uint32_t value, bool paused);
private:
    DashboardView& view;
};
#endif
