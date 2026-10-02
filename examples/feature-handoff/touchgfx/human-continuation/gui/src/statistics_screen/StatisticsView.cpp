// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/statistics_screen/StatisticsView.hpp>
#include <touchgfx/Unicode.hpp>

StatisticsView::StatisticsView()
{

}

void StatisticsView::setupScreen()
{
    StatisticsViewBase::setupScreen();
}

void StatisticsView::tearDownScreen()
{
    StatisticsViewBase::tearDownScreen();
}

void StatisticsView::function1()
{
    presenter->resetStatistics();
}

void StatisticsView::showState(uint32_t value, bool paused, const epw_stats_result& statistics)
{
    touchgfx::Unicode::snprintf(counterValueBuffer, COUNTERVALUE_SIZE, "%u", static_cast<unsigned>(value));
    touchgfx::Unicode::snprintf(pausedValueBuffer, PAUSEDVALUE_SIZE, "%u", paused ? 1U : 0U);
    touchgfx::Unicode::snprintf(sampleCountValueBuffer, SAMPLECOUNTVALUE_SIZE, "%u", static_cast<unsigned>(statistics.count));
    if (statistics.count == 0U)
    {
        touchgfx::Unicode::snprintf(minimumValueBuffer, MINIMUMVALUE_SIZE, "--");
        touchgfx::Unicode::snprintf(maximumValueBuffer, MAXIMUMVALUE_SIZE, "--");
        touchgfx::Unicode::snprintf(meanValueBuffer, MEANVALUE_SIZE, "--");
    }
    else
    {
        touchgfx::Unicode::snprintf(minimumValueBuffer, MINIMUMVALUE_SIZE, "%u", static_cast<unsigned>(statistics.minimum));
        touchgfx::Unicode::snprintf(maximumValueBuffer, MAXIMUMVALUE_SIZE, "%u", static_cast<unsigned>(statistics.maximum));
        touchgfx::Unicode::snprintf(meanValueBuffer, MEANVALUE_SIZE, "%u", static_cast<unsigned>(statistics.mean));
    }
    counterValue.invalidate();
    pausedValue.invalidate();
    sampleCountValue.invalidate();
    minimumValue.invalidate();
    maximumValue.invalidate();
    meanValue.invalidate();
}
