// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#ifndef STATISTICSVIEW_HPP
#define STATISTICSVIEW_HPP

#include <gui_generated/statistics_screen/StatisticsViewBase.hpp>
#include <gui/statistics_screen/StatisticsPresenter.hpp>
#include <epw_stats.h>

class StatisticsView : public StatisticsViewBase
{
public:
    StatisticsView();
    virtual ~StatisticsView() {}
    virtual void setupScreen();
    virtual void tearDownScreen();
    virtual void function1() override;
    void showState(uint32_t value, bool paused, const epw_stats_result& statistics);
protected:
};

#endif // STATISTICSVIEW_HPP
