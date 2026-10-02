// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#ifndef MODEL_HPP
#define MODEL_HPP
#include <stdint.h>
#include <epw_stats.h>
class ModelListener;
class Model {
public:
    Model();
    void bind(ModelListener* listener) { modelListener = listener; }
    void tick();
    void togglePause();
    uint32_t value() const { return count; }
    bool paused() const { return isPaused; }
    epw_stats_result statistics() const;
protected:
    ModelListener* modelListener;
private:
    uint32_t count;
    uint16_t frameCount;
    bool isPaused;
    uint32_t sampleStorage[8];
    epw_stats sampleWindow;
    void notify();
};
#endif
