# Original ZCU102 MPSoC handoff case

This case preserves one current BD across native hardware export and software
handoff. The design contract is in [PROJECT.md](PROJECT.md). It uses an actual
Zynq UltraScale+ MPSoC PS, SmartConnect, dual AXI GPIO and an original counter
module reference; it does not replace the interconnect or GPIO with handwritten
AXI logic.

Use this directory with the complete `examples/vivado` tree. The runner imports
the unchanged v0.3 process cleanup, timeout and atomic-JSON helpers from
`controlled-project/scripts/run_clock.py`. Tool binaries and vendor sources are
provided by the user's existing 2025.1 installation. No tools are downloaded.

## Offline native commands

Run from the repository root, substituting existing tools and new ASCII output
directories outside the repository:

For the standalone Vivado ZIP, enter its `vivado` directory and replace the
leading `examples/vivado/` in these commands with the corresponding local path.

```text
python -B examples/vivado/soc-handoff/scripts/run.py prepare --vivado <Vivado/bin/vivado.bat> --output <new-A-directory>
python -B examples/vivado/soc-handoff/scripts/run.py sim --vivado <Vivado/bin/vivado.bat> --output <new-simulation-directory>
python -B examples/vivado/soc-handoff/scripts/run.py sim-missing-clear --vivado <Vivado/bin/vivado.bat> --output <new-negative-directory>
python -B examples/vivado/soc-handoff/scripts/run.py sim-missing-pause --vivado <Vivado/bin/vivado.bat> --output <another-new-negative-directory>
python -B examples/vivado/soc-handoff/scripts/run.py address-overlap --vivado <Vivado/bin/vivado.bat> --output <new-address-negative-directory>
```

To isolate the overlap check from baseline creation, `address-overlap` also
accepts `--project <validated-case/project/soc_handoff.xpr>`. It first checks
the ownership and source/output paths, copies the project and current counter
source into the new output, and mutates only that disposable copy. The original
input remains unchanged. The attempted overlap uses the current original GPIO's
base/range, not a second hardcoded address source.

Preparation creates `project/soc_handoff.xpr`, validates the BD, produces IP
outputs and wrapper, synthesizes the top, exports `hardware.xsa` without a
bitstream, and runs installed SDTGen to create `sdt/system-top.dts` with its
include files. These are separate recorded stages; a failed stage leaves later
stages `NOT_RUN`. Native Tcl scope failures observed during development are
preserved in local evidence, not treated as successful generation.

The existing-project path uses the **saved current design**:

```text
python -B examples/vivado/soc-handoff/scripts/run.py export --vivado <Vivado/bin/vivado.bat> --project <owned-case-directory/project/soc_handoff.xpr> --output <new-export-directory>
```

This is a narrow original-case runner, not a general project importer. The
ownership marker, source references and project layout must match this case.
Projects, output directories and inputs must have no symlinks or junctions.
The output must be separate from both source and project trees. Export can
regenerate project files, but never calls the preparation Tcl or assigns an
address. Reports are outside the maintained project. Before human editing,
retain an immutable baseline snapshot and a separate complete working copy.

The [current-design reconstruction entry](CURRENT_REBUILD.md) preserves saved
BD inputs and explains the source and verification boundaries. For an
**empty-directory reconstruction**, the native mechanism is to
create a new project using the current saved project's device/board, add the
current original counter RTL, and `import_files` the current saved BD. Then
validate that imported design, generate output products, make the wrapper,
synthesize and export XSA/SDT. Record the current input hashes and verify the
imported BD still describes those inputs. Do not invoke `prepare.tcl`, rebuild
the graph from its initial address, copy stale XSA/SDT, or reuse an earlier
PASS as evidence for this fresh build. This paragraph documents the mechanism;
it does not claim a future user's edit or its fresh reconstruction has run.

Each native process has a default 900-second timeout (`--timeout` accepts only
positive finite values). The runner records real exit codes and logs, writes
JSON through same-directory atomic replacement, and limits timeout/interruption
cleanup to its own still-live PID tree. Failures return 1, parameter errors 2,
and controlled interrupts 130. A cleanup failure remains incomplete evidence.
Power loss, force-kill and persistent storage failure cannot guarantee a final
record; inspect actual files when resuming.

## Evidence levels

RTL simulation checks actual counter source for reset, clear priority, stopped
and paused behavior, resume and wrap. The wrap test deposits a boundary value;
it does not simulate 2^32 cycles. Negative copies remove clear or pause behavior
and must fail a counter assertion, not merely fail to launch a tool.

The disposable overlap fixture adds a second GPIO and SmartConnect output only
to attempt an overlapping address assignment. The positive and human-maintained
designs still contain exactly one GPIO. A separate unassigned-address diagnostic
showed that Vivado 2025.1 reports BD 41-1356 / 41-2909 as critical warnings but
returns success from validation; this is not recorded as native rejection. The
strict `address-unassigned` experiment therefore remains a failed experiment.

BD/XSA/SDT presence alone does not prove their semantic consistency. The
independent handoff checker must inspect those actual files and their source
identity. The native runner explicitly reports this check as `NOT_RUN` until a
separate checker result is supplied. No stage proves AXI transactions occurred
on an A53, that implementation timing closed, or that a board ran.

Original Tcl, RTL, Python and testbench sources use the repository MIT license.
Do not redistribute the local vendor framework, generated IP, XSA, generated
SDT, full project or private raw logs as original source.

## Preparation evidence, 2026-10-02

The original A baseline completed actual BD validation, IP output generation,
wrapper generation, top synthesis, XSA export without bitstream and SDT
generation; the three native stages returned 0. An independent checker passed
the actual BD/XSA/SDT address, range, GPIO shape and source-identity checks.
Counter XSim passed 18 checks. Removing clear triggered `CLEAR_DOMINANCE` at
86 ns; removing pause triggered `PAUSE_HOLD` at 26 ns; each native process
returned 1 and the runner matched that specific business failure. The actual
overlap attempt was refused with `BD 41-1075` and native return code 1.

A 417-file verified archive and separate complete human working copy were
created locally. They are not distributed vendor artifacts. The preparation
agent made no subsequent human address edit and supplied no precomputed
continuation result. See [validation-20261002.json](validation-20261002.json)
for source identities and stage distinctions. Later runner hardening has its
own current source identity and host checks; A's historical native success is
not silently relabelled as a rerun of every final script revision.

Several initial runs failed in Vivado's native Tcl IP GUI scope creation,
including a subsequent single-threaded overlap-preparation run. Read/source
diagnostics did not establish a corrupt vendor file or an external environment
override. A later successful baseline and successful negative checks do not
prove that native failure's root cause is fixed. The initial clock metadata
mismatch was a separate source error and was corrected to the board-preset
derived value before the successful A baseline.

## Human continuation and reconstruction, 2026-10-02

The user saved the GPIO base as `0xA0010000`, keeping the 64 KiB range.
A fresh-context agent read the current design and continued in a new copy.
Its B native generation/synthesis/XSA and SDT stages completed; an overly
broad wrapper-retention check initially failed on a generated Date comment.
The original FAIL was preserved and the repaired check was separately applied
to the actual products. The original counter bytes and user inputs were kept.

The current saved BD was then imported into an empty project. C3 completed
native import/products, synthesis/XSA and SDT, and its separate BD/XSA/SDT
checker passed. Native provenance and one previously implicit PS parameter
required a repaired post-reader: the actual final post-validation passed using
complete B/C effective parameter and address evidence. Raw differences and
earlier failures remain in the records. This is not a claim that the final
script revision was rerun through every native stage.

See [continuation results](validation-continuation-20261002.json),
[real stale-artifact combinations](validation-handoff-20261002.json) and
[host negative tests](validation-host-20261002.json). The explicit
[post-validation procedure](CURRENT_REBUILD.md) never rewrites a native result.
Platform/BSP/A53 application builds, implementation, bitstream and board
operations remain NOT_RUN. Counter XSim evidence is from the unchanged
baseline RTL, not a new PS transaction simulation.
