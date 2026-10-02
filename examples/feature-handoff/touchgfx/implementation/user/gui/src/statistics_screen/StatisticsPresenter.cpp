// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/statistics_screen/StatisticsView.hpp>
#include <gui/statistics_screen/StatisticsPresenter.hpp>

StatisticsPresenter::StatisticsPresenter(StatisticsView& v)
    : view(v)
{

}

void StatisticsPresenter::activate()
{
    view.showState(model->value(), model->paused(), model->statistics());
}

void StatisticsPresenter::stateChanged(uint32_t value, bool paused)
{
    view.showState(value, paused, model->statistics());
}

void StatisticsPresenter::deactivate()
{

}
