# Handoff state

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT

Current stage: **READY_FOR_HANDOFF**. The source inputs contain only two idle task entries and a handle-creation check. No sample generator, queue transfer, rolling statistics, dropped-send counter, or functional acceptance test has been implemented.

Future goal and preserved design choices: see `PROJECT.md` and the authoritative `sample_statistics.ioc`. The independent implementation stage starts from `Services/Sampling` and `Domain/Statistics`, preserves native object ownership/order, and implements cyclic 10..90 samples every 10 RTOS ticks through `SampleQueue`, a rolling window of 8 received samples, and a separate failed-send count.

Native baseline evidence is stored outside this repository, under the isolated run's `tool-trials/cubemx/baseline-02/reports/result.json` (**PASS**). The original tool-generated work project is `tool-trials/cubemx/baseline-02/work/sample_statistics`; preserve it and take a fresh copy for feature implementation. The sibling `tool-trials/cubemx/TOOLCHAIN.md` records installed paths and the exact native commands, so the next agent does not need earlier private history.

Verified on 2026-09-30: CubeMX native generation exit 0; Keil bootstrap and final native rebuild exits 0; final **0 errors / 0 warnings**. Final compilation inputs were identical before and after rebuild. MAP links `SampleFeed_Entry` to `sample_feed.o` and `StatsWorker_Entry` to `statistics_worker.o`, with `SampleFeedStack` **1024 bytes** and `SampleQueueStorage` **48 bytes**. Native creation order remains `SampleQueue`, `SampleFeed`, `StatsWorker`; the two entries are external and owned by their separate user files. Generated code outside native USER CODE regions was preserved. The original preparation script, IOC and user source hashes, adapter hash, input snapshots, native logs/journal, and MAP/AXF copies are in that report directory.

The retained `baseline-01` attempt correctly failed the source-stability check after Keil rewrote its own generated `RTE_Components.h` on first cold build. `baseline-02` records that header-only bootstrap change separately, then verifies stable inputs during the final rebuild. Do not use the earlier FAILED result as the handoff baseline.

Next: implement the shared `epw_stats` API described in `PROJECT.md` and wire it through the existing tasks/queue in a fresh copy; add the resulting core to the actual target build; validate behavior using independent host contracts plus fresh native build/source/entry evidence. Do not call `prepare.py` as an updater over that feature project: it intentionally creates idle original fixtures only. The untouched native baseline includes the preparation-time copy of this state file; use this final handoff state and its linked receipt for current completion status. Runtime and board evidence remain **NOT_RUN**.
