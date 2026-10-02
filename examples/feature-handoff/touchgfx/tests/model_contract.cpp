// SPDX-License-Identifier: MIT
// Copyright (c) 2026 YuWYY
#include <gui/model/Model.hpp>
#include <gui/model/ModelListener.hpp>
#include <cstdio>

#define CHECK(c) do { if(!(c)) { std::fprintf(stderr,"model contract failure line %d: %s\n",__LINE__,#c); return 1; } } while(0)

static void ticks(Model& m, unsigned n) { for(unsigned i=0;i<n;++i) m.tick(); }

int main()
{
    Model m;
    CHECK(m.value()==0 && !m.paused() && m.statistics().count==0);
    ticks(m,59);
    CHECK(m.value()==0 && m.statistics().count==0);
    m.tick();
    CHECK(m.value()==1 && m.statistics().count==1 && m.statistics().mean==1);
    ticks(m,7*60);
    epw_stats_result s=m.statistics();
    CHECK(s.count==8 && s.minimum==1 && s.maximum==8 && s.mean==4);
    ticks(m,17);
    m.togglePause();
    ticks(m,100);
    CHECK(m.paused() && m.value()==8 && m.statistics().mean==4);
    ModelListener next;
    next.bind(&m);
    m.bind(&next);
    CHECK(m.paused() && m.value()==8 && m.statistics().count==8);
    m.togglePause();
    ticks(m,42);
    CHECK(m.value()==8);
    m.tick();
    s=m.statistics();
    CHECK(m.value()==9 && s.count==8 && s.minimum==2 && s.maximum==9 && s.mean==5);
#if EPW_WITH_RESET
    ticks(m,13);
    m.togglePause();
    m.resetStatistics();
    s=m.statistics();
    CHECK(s.count==0 && s.minimum==0 && s.maximum==0 && s.mean==0);
    CHECK(m.paused() && m.value()==9);
    ticks(m,100);
    CHECK(m.statistics().count==0 && m.value()==9);
    m.togglePause();
    ticks(m,46);
    CHECK(m.value()==9 && m.statistics().count==0);
    m.tick();
    s=m.statistics();
    CHECK(m.value()==10 && s.count==1 && s.minimum==10 && s.maximum==10 && s.mean==10);
#endif
    std::puts("model contract PASS");
    return 0;
}
