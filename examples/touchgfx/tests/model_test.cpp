// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/model/Model.hpp>
#include <gui/model/ModelListener.hpp>
#include <cstdio>
#include <cstring>

struct Observer : ModelListener {
    unsigned events;
    uint32_t last;
    bool lastPaused;
    Observer() : events(0), last(0), lastPaused(false) {}
    virtual void stateChanged(uint32_t value, bool paused) {
        ++events; last = value; lastPaused = paused;
    }
};
static bool expect(bool truth, const char* name) {
    if (!truth) { std::fprintf(stderr, "FAIL: %s\n", name); }
    return truth;
}
static void frames(Model& m, unsigned count) { while (count--) { m.tick(); } }

int main(int argc, char** argv) {
    Model m;
    Observer first;
    m.bind(&first); first.bind(&m);
    if (argc == 2 && std::strcmp(argv[1], "--inject-extra-period") == 0) {
        frames(m, 60);  // Controlled stimulus error; the unchanged oracle must reject it.
    }
    if (!expect(m.value() == 0 && !m.paused() && first.events == 0, "startup")) return 1;
    frames(m, 59);
    if (!expect(m.value() == 0 && first.events == 0, "partial period")) return 1;
    frames(m, 1);
    if (!expect(m.value() == 1 && first.events == 1 && first.last == 1, "first period")) return 1;
    frames(m, 17);
    m.togglePause();
    if (!expect(m.paused() && first.events == 2 && first.lastPaused, "pause notification")) return 1;
    frames(m, 120);
    if (!expect(m.value() == 1 && first.events == 2, "paused time does not count")) return 1;
    Observer second;
    m.bind(&second); second.bind(&m);
    if (!expect(m.value() == 1 && m.paused() && second.events == 0, "screen rebind preserves state")) return 1;
    m.togglePause();
    frames(m, 42);
    if (!expect(m.value() == 1 && second.events == 1 && !second.lastPaused, "resume retains partial period")) return 1;
    frames(m, 1);
    if (!expect(m.value() == 2 && second.events == 2 && second.last == 2, "resume period")) return 1;
    m.bind(0);
    frames(m, 60);
    if (!expect(m.value() == 3, "unbound listener")) return 1;
    // Reach the documented display limit using the real implementation.
    frames(m, 60U * 1000000U);
    if (!expect(m.value() == 999999U, "display limit saturates")) return 1;
    frames(m, 600);
    if (!expect(m.value() == 999999U, "limit stays stable")) return 1;
    std::puts("PASS: model startup, periods, pause/resume, observer handover, absent observer, saturation");
    return 0;
}
