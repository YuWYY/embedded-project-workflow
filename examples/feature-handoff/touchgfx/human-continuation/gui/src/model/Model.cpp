// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/model/Model.hpp>
#include <gui/model/ModelListener.hpp>
Model::Model() : modelListener(0), count(0), frameCount(0), isPaused(false) {
    epw_stats_init(&sampleWindow, sampleStorage, 8U);
}
epw_stats_result Model::statistics() const {
    epw_stats_result result;
    epw_stats_read(&sampleWindow, &result);
    return result;
}
void Model::notify() {
    if (modelListener) { modelListener->stateChanged(count, isPaused); }
}
void Model::tick() {
    if (isPaused) { return; }
    if (++frameCount == 60U) {
        frameCount = 0;
        if (count < 999999U) {
            ++count;
            epw_stats_push(&sampleWindow, count);
        }
        notify();
    }
}
void Model::togglePause() {
    isPaused = !isPaused;
    notify();
}
void Model::resetStatistics() {
    // Clear the window only; count, pause and the partial period continue unchanged.
    epw_stats_reset(&sampleWindow);
    notify();
}
