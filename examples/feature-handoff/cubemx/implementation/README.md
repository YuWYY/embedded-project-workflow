# Sample statistics implementation

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT

This directory contains the feature-stage user code. The sibling original
`Services`, `Domain`, IOC and `prepare.py` remain the idle baseline inputs.
The only statistics implementation is `examples/common/rolling-stats/epw_stats.c`;
the Keil project references that source and its header directly, without copying
them into a vendor tree. The shared core has no platform or heap dependency.

## Behavior and ownership

| Function | Owner | Observable behavior |
| --- | --- | --- |
| Sampling sequence and cadence | `Services/Sampling/sample_feed.c` | First release 10 RTOS ticks after entry; absolute tick deadlines then advance by 10. Attempted samples cycle 10 through 90, including after a failed send. |
| Queue transfer | Existing native `SampleQueue` | Nonblocking producer put; consumer waits for messages. No other raw-sample channel. |
| Rolling window | `Domain/Statistics/statistics_worker.c` | Only successful queue receives enter the 8-element window. Count warms up from 1 to 8, then oldest values are replaced. Minimum, maximum and integer mean describe that window. |
| Creation and resource ownership | Existing IOC and generated RTOS code | Original two tasks, mixed allocation, queue storage and creation order remain unchanged. No added RTOS objects. |

The producer advances the sequence on each send attempt. Queue rejection increments
`failed`; it does not enter the consumer's window. A rejected/past absolute delay
increments `missed_releases` and restarts the release cadence from the current tick,
avoiding a burst of catch-up sends. These are RTOS ticks, not a millisecond conversion.

`Sampling_Read()` returns a coherent task-context snapshot of attempted/sent/failed
sends and missed releases. `Statistics_Read()` returns a coherent task-context
snapshot of count/minimum/maximum/mean, total received and receive errors; before
the first receive it returns false with zero window fields. Both reject NULL
outputs. Snapshot copies and their updates use short FreeRTOS critical sections;
the queue operations and statistics scan run outside them. Callers must not invoke
these getters from interrupts. Counters wrap modulo 2^32. The two separate snapshots
are not one transaction, so an observer can see a consumer update before the producer
has published the corresponding sent counter. The counters are diagnostics, not
another data-transfer path.

The statistics state/storage remain private to the consumer. With no loss, samples
10..80 give count 8, minimum 10, maximum 80, mean 45. Sample 90 replaces 10 and gives
minimum 20, maximum 90, mean 55. The next 10 replaces 20 and gives minimum 10,
maximum 90, mean 53. No success indicator represents target execution.

## Reproduce from a validated baseline

Use an existing native idle `sample_statistics` baseline from the original
`prepare.py`, a new work directory and a separate new reports directory outside
the repository. The baseline must still be untouched; this command copies it first.

```text
python -B examples/feature-handoff/cubemx/implementation/apply.py
  --baseline <native-idle-sample_statistics-directory>
  --work-root <new-isolated-work-directory>
  --reports <new-isolated-reports-directory>
  --cubemx <installed-STM32CubeMX.exe>
  --firmware <installed-STM32Cube_FW_G4_V1.6.3-directory>
  --uv4 <installed-UV4.exe>
  --armcc <installed-armcc.exe>
  --pack <installed-STM32G4xx_DFP-2.0.0-directory>
```

Join the example command lines for your shell. `--help` lists all arguments.
The project-specific entry copies only these user task modules over the copied
idle modules, adds the shared source and include path to the existing Keil target,
then invokes native CubeMX regeneration followed by `UV4 -r`. It requires generator
retention of user regions/files, all Core non-user bodies, configuration semantics
and source bindings; it does not repair generated code to manufacture a pass.
Installed tool identities, native process exits, source hashes (including the
external core), unchanged build inputs, fresh MAP/AXF and linked owners are archived.
Failures remain in that attempt's report. A fresh retry uses new destinations;
`--resume` instead validates an existing feature work copy with a new reports
directory and refuses to overwrite user modules that differ from this package.
Before any resumed-project write or tool invocation, the entry validates the
current IOC, generator bookkeeping (`.mxproject`), compiler sources/includes,
scatter inputs and output directories. The shared source/header are the only
external compiler dependencies and are hash-bound; generator-owned deletion
paths and build outputs must remain inside the current project. Unknown metadata
fields, custom flags and enabled nonempty hooks remain rejected.
An unchanged generated C file may retain its timestamp; completion therefore
requires this invocation's explicit generated-file/OK log, a fresh native project
file, expected outputs, and the full content/binding retention checks.

The existing `cubemx_rtos.py` is unchanged. Its narrow project inspection is used
only for the copied-input baseline, before adding the external core. The separate
feature entry explicitly validates this project's one external source/include root
and includes both files in its source-stability evidence. This is a project-specific
build integration, not a new generic adapter support claim.

For later native generation, use the saved `generation.mxscript` and keep the same
relative repository location or adjust the shared-core source/include references.
The generated Keil project must still compile `sample_feed.c`, `statistics_worker.c`
and `epw_stats.c` once each. For a rebuild use the local tool record's `UV4 -r` command.
The original `prepare.py` must never be used as an updater over a feature project.

The independent host contract tests validate the shared C API separately. Native
rebuild/MAP evidence demonstrates compilation and linking; task scheduling, actual
queue backpressure, tick timing and stack watermarks require separately authorized
target execution. No flash/debug/serial/hardware operation is provided here.

The focused host-only preflight regression can be run without launching native
tools. Provide the original native baseline, an existing feature project, a saved
installation receipt and a new isolated output directory:

```text
python -B examples/feature-handoff/cubemx/implementation/tests/check_resume_boundary.py
  --baseline <native-idle-sample_statistics-directory>
  --project <existing-feature-sample_statistics-directory>
  --installation <saved-installation.json>
  --output <new-isolated-test-output-directory>
```

It copies the feature project, injects path/metadata drift, and requires rejection
before mutation or native dispatch. A legitimate resume must reach an intercepted
generation call. All native processes are forbidden by the test harness.
