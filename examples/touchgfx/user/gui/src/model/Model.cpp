// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/model/Model.hpp>
#include <gui/model/ModelListener.hpp>
Model::Model() : modelListener(0), count(0), frameCount(0), isPaused(false) {}
void Model::notify() {
    if (modelListener) { modelListener->stateChanged(count, isPaused); }
}
void Model::tick() {
    if (isPaused) { return; }
    if (++frameCount == 60U) {
        frameCount = 0;
        if (count < 999999U) { ++count; }
        notify();
    }
}
void Model::togglePause() {
    isPaused = !isPaused;
    notify();
}
