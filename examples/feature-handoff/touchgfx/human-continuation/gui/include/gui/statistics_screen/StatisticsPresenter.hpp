// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#ifndef STATISTICSPRESENTER_HPP
#define STATISTICSPRESENTER_HPP

#include <gui/model/ModelListener.hpp>
#include <mvp/Presenter.hpp>

class StatisticsView;

class StatisticsPresenter : public touchgfx::Presenter, public ModelListener
{
public:
    StatisticsPresenter(StatisticsView& v);

    /**
     * The activate function is called automatically when this screen is "switched in"
     * (ie. made active). Initialization logic can be placed here.
     */
    virtual void activate();

    /**
     * The deactivate function is called automatically when this screen is "switched out"
     * (ie. made inactive). Teardown functionality can be placed here.
     */
    virtual void deactivate();
    virtual void stateChanged(uint32_t value, bool paused);
    void resetStatistics();

    virtual ~StatisticsPresenter() {}

private:
    StatisticsPresenter();

    StatisticsView& view;
};

#endif // STATISTICSPRESENTER_HPP
