# Statistics feature: first handoff snapshot

This is the authored source snapshot immediately before the HUMAN Reset edit.
It is not an installer for an active/human-modified project. The original
`../user/` and CounterHandoff baseline are retained. No vendor framework, fonts,
generated base classes, native logs, objects or binaries are packaged here.

## Behavior and source ownership

The current native source is `StatisticsHandoff.touchgfx`, with Dashboard,
Controls and Statistics. Controls opens Statistics; Statistics returns to Controls.
The startup, 480 x 272 RGB565 format, existing Dashboard/Controls logic, 60 unpaused
GUI-tick cadence, 999999 saturation and partial-period pause semantics are retained.

Only a genuine counter increment pushes the new count into an eight-sample window.
Pause does not advance the period or window; navigation does not clear either.
Statistics displays current count, paused state, samples, min, max and integer mean.
An empty window shows samples=0 and min/max/mean=0. This is distinguished from a
non-empty zero window by the sample count. GUI ticks are not a measured wall clock.

The Model owns `epw_stats` and its eight-element caller storage. Its
`epw_stats_result statistics() const` returns a read-only value snapshot.
StatisticsPresenter reads that snapshot on activation and on the existing
`ModelListener::stateChanged` notification; StatisticsView formats numeric
TouchGFX Unicode wildcard buffers and invalidates the affected text widgets.
No new polling loop, alternate page framework or generated-source patch exists.

Core files are byte-identical to `../../../common/rolling-stats/epw_stats.c,h`.
The C file lives at `user/gui/src/core/epw_stats.c`; the header lives at
`user/gui/include/epw_stats.h`, which is already on the native include path.
The native makefile recursively finds `.c` sources below `gui/src`.
`IDENTITY.json` records the common/core copies and authored-source SHA-256 values.
The shared core has a reusable reset API; this phase adds no UI Reset control,
native reset interaction, generated reset virtual, or Model/View reset behavior.

## Reproduce this phase in a new disposable directory

These steps are only for a new reproduction directory. For continuing actual user
work, read its current `.touchgfx`/texts/user files and use the existing-project
runner directly. Never restore this snapshot over the human-edited continuation.

1. Copy the prepared CounterHandoff baseline tree to a brand-new directory. If
   no prepared baseline exists, use `../setup.py` once to create that baseline
   in a new directory, according to `../PROJECT.md`.
2. In the new copy only, rename `CounterHandoff.touchgfx` to
   `StatisticsHandoff.touchgfx`. Copy this snapshot's same-named native file,
   `application.config`, and `texts.xml` to the corresponding native file,
   `application.config`, and `assets/texts/texts.xml`. Overlay this snapshot's
   `user/gui/` on the new copy's `gui/`. Do not alter native generated sources,
   build scripts or the original baseline. The Common Frontend user template
   files already in the baseline remain; no vendor tree is distributed here.
3. Close/save any concurrent Designer writer, then invoke the installed native
   tool through the current existing-project entry. From the candidate root:

   ```powershell
   python -B skills/embedded-project-workflow/scripts/touchgfx_project.py inspect --project "<统计工程目录>" --touchgfx-root "<TouchGFX安装目录>"
   python -B skills/embedded-project-workflow/scripts/touchgfx_project.py build --project "<统计工程目录>" --touchgfx-root "<TouchGFX安装目录>" --reports "<新统计构建报告目录>"
   ```

   Reports must be new, outside the project/install, and on the project volume.
   Build includes fresh generation and a clean Simulator build. It checks the
   current user source/config identities and never restores this snapshot.

## HUMAN continuation

Use a new copy of the completed Statistics project so this phase stays a baseline.
Open that copy's `StatisticsHandoff.touchgfx` in TouchGFX Designer 4.26.1.

1. Select **Statistics**. Add a visible button in the reserved rectangle
   **x=260, y=132, width=200, height=48**. Set its name to **resetButton** and
   displayed text to **Reset**.
2. Add an interaction triggered when **resetButton is clicked**. Select
   **Call new virtual function**, with function name **resetStatistics**.
3. Save the native project and text resources. Report the saved file path to the
   next implementation agent. The next agent re-reads the latest design, uses
   actual generation, then connects the generated callback in user View/Presenter/
   Model. Preserve the HUMAN control and interaction; do not copy this phase over it.

The earlier baseline preparation note named Controls for this reserved area.
That was a page-name typo in preparation, not a changed user requirement.
This phase uses Statistics, as requested; Controls also retains its old empty area.

## Evidence and remaining validation

The isolated run used actual TouchGFX 4.26.1 generation and clean simulator build.
Both subprocesses returned 0 and user source/config preservation passed. Native
reports remain outside the package under `tool-trials/touchgfx/`:
`statistics-generate-01/results.json` and `statistics-build-01/results.json`.
There were no native failures in this feature phase; prior baseline failed reports
remain unchanged. All 699 original CounterHandoff files matched their pre-copy
SHA-256 identities. `IDENTITY.json` records the built executable identity without
distributing it.

Simulator GUI interaction and hardware operation were not executed in this phase.
Independent host checks are reported separately by the coordinator; this README
does not substitute generation/build for behavior or on-screen evidence.

For the later actual simulator check, pause on Controls and verify a Statistics
snapshot remains stable; navigate away/back and verify retention; resume and check
samples saturate at eight and that min/max/mean match the last eight increments.
For count N >= 8 in the untouched initial run, min=N-7, max=N, and mean=N-4.
The human continuation then adds its own Reset interaction checks.
