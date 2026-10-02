// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#ifndef SETTINGSPRESENTER_HPP
#define SETTINGSPRESENTER_HPP
#include <gui/model/ModelListener.hpp>
#include <mvp/Presenter.hpp>
class ControlsView;
class ControlsPresenter : public touchgfx::Presenter, public ModelListener {
public:
    explicit ControlsPresenter(ControlsView& v);
    virtual ~ControlsPresenter() {}
    virtual void activate();
    virtual void deactivate() {}
    virtual void stateChanged(uint32_t value, bool paused);
    void togglePause();
private:
    ControlsView& view;
};
#endif
