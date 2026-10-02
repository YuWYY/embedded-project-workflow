// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#ifndef MODELLISTENER_HPP
#define MODELLISTENER_HPP
#include <gui/model/Model.hpp>
class ModelListener {
public:
    ModelListener() : model(0) {}
    virtual ~ModelListener() {}
    void bind(Model* m) { model = m; }
    virtual void stateChanged(uint32_t, bool) {}
protected:
    Model* model;
};
#endif
