# Human TouchGFX continuation source overlay

This authored source snapshot continues a saved HUMAN edit in TouchGFX 4.26.1 /
Simulator 2.0.0, 480 x 272, RGB565. It is an overlay for a native Simulator project;
the vendor framework, font file, generated classes, toolchain, native template
scaffolding and executable are intentionally not distributed here.

The HUMAN edit owns Statistics.resetButton at (414, -2), size 50 x 50, and
Interaction1: click resetButton -> function1. Those values and every pre-existing
native component, interaction and navigation remain unchanged. The top two pixels
of the button remain outside the screen, as in the saved HUMAN input.

AI added the native resetLabel TextArea, ResetLabel text, 12-pixel ResetButton
typography, the default '-' wildcard glyph, and the user implementation chain:
generated function1 -> StatisticsView::function1 -> StatisticsPresenter::resetStatistics
-> Model::resetStatistics -> existing epw_stats_reset. AI did not create the HUMAN
button or function1 interaction. A 33-pixel generated text advance fits the 40-pixel
caption area inside the existing border; this glyph metric is not an image-based visual check.

Reset clears only the eight-sample window. Count, paused state and partial 60-active-
tick sampling period remain. Samples is 0 and Min / Max / Mean show -- while empty.
Sampling then resumes with the next actual increment from the retained count.
The existing shared statistics core is copied unchanged.

Native validation used the Skill's existing-project touchgfx_project.py build
entry, which performed actual generation and a clean Simulator build from the
current native file. Both vendor commands returned 0 and source retention passed.
Headless checks compiled the actual Model/core and linked the native Unicode
implementation; they covered paused/running reset, notification, retained partial
periods, repeated reset, listener rebinding, sample continuation and window rollover.
These checks are not GUI clicks or hardware evidence.

To recreate: start with a locally installed Simulator 2.0.0 template, apply this
source overlay, use the installed Verdana font through Designer, save and close
Designer, then run the Skill's existing-project build command with that project,
the local TouchGFX tool root and a new sibling reports directory. Native resources
and bases must be generated; do not patch generated outputs.

User GUI evidence on 2026-09-30: the user reported "五项均通过" (all five
checks passed) for actual Simulator interaction: statistics update, paused Reset to
zero samples and no-data, preserved count/pause, navigation retention, and resumed
sampling from current progress. The report is bound to the final native config,
simulator executable, Model.cpp and StatisticsView.cpp hashes in validation.json.
This is USER-reported evidence, not an agent-observed click trace. The agent did not
launch or click the GUI. A separate visual assessment of the small caption and a
running-Reset GUI case were not included in those five user checks; running reset
is covered by the actual Model host test. No target build or hardware ran.

validation.json records sanitized evidence and actual source hashes. MANIFEST.json
hashes every delivered file except itself. Its identity is SHA-256 of the UTF-8
canonical file-to-SHA256 JSON map (sorted keys, compact separators).
