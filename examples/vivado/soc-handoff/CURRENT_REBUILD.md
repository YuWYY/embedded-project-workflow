# Rebuild the saved current design

The maintenance source is the user's current saved BD, together with the XPR
resource properties and original `counter32.v`. The initial `prepare.tcl` is
not used by this entry point.

```text
python -B examples/vivado/soc-handoff/scripts/rebuild_current.py --vivado <2025.1/Vivado/bin/vivado.bat> --project <owned-current-case/project/soc_handoff.xpr> --output <new-empty-ASCII-directory> --timeout 900
```

This narrow importer accepts the existing original case ownership marker and
layout. It reads part, board part, top and source references from the supplied
XPR; it does not substitute the initial address. It copies the original counter
RTL and imports the current saved `system.bd` through Vivado `import_files`.
Additional empty BDs are retained as source files. Nonempty additional designs,
user constraints, extra user HDL and custom hooks require an explicit adapter;
they are not silently dropped. Custom defines/generics/include configuration,
nondefault libraries, altered source-use flags and explicit per-file compiler
overrides are rejected before creating output or launching Vivado.

The output directory is new or empty. No previous project, generated XCI,
wrapper, DCP, XSA or SDT is used as a build product. Vivado creates the project,
validates the imported design, generates IP products and its managed wrapper,
then the existing `export.tcl` performs current top synthesis and exports XSA
without bitstream. Installed SDTGen consumes that exact XSA. Original inputs
are read only; generated products live under the new output.

`result.json` records input and copied-source identities, per-process command,
actual exit code and timeout, XSA/SDT product integrity, preserved BD list and
semantic comparison. Native logs are in `reports/<stage>/stdout.log`. The
semantic comparison includes component versions and parameters, interfaces,
ports, all nets, clock/reset metadata and address spaces. It omits only native
validation bookkeeping and generated output locations; differing source hashes
are retained. `imported_sources.txt` records the recreated project's sources
and synthesis compile order. Native output creation is not evidence of A53
MMIO transactions or board operation.

The original counter must retain identical bytes and remain a current project
source. Vivado owns the generated `system_wrapper.v`; it is recreated. A source
snapshot includes that old wrapper solely as provenance, not as rebuilt logic.
Empty `design_1.bd`, when present in the user's XPR, is retained while
`system_wrapper` remains the top. A separate current BD/XSA/SDT semantic check
is still required and is explicitly recorded as `NOT_RUN` by this runner.

Each native process is bounded by the supplied timeout (default 900 seconds).
Records are written before launch; failed and later `NOT_RUN` stages remain
visible. Software platform, BSP, A53 application build, implementation,
bitstream and hardware operations are explicitly `NOT_RUN` in this workflow.
Run the entry point in its source tree: the script copies in the output are
execution provenance and still depend on the repository's shared runner.

## Explicit post-validation of completed native artifacts

A native import may record previously implicit PS settings explicitly. The
ordinary rebuild preserves the resulting raw BD differences and fails its
strict comparison; it does not guess that an absent field means a default.
To inspect an already completed native run against a current native reference:

```text
python -B examples/vivado/soc-handoff/scripts/rebuild_current.py --post-validate --vivado <2025.1/Vivado/bin/vivado.bat> --project <fixed-source/project/soc_handoff.xpr> --output <completed-rebuild-directory> --reference-project <current-B/project/soc_handoff.xpr> --reference-xsa <current-B-export/hardware.xsa>
```

This launches no native tools. It writes a new `post-validation.json` and
refuses to overwrite an existing one. The original `result.json`, exit code,
native execution scripts and hashes remain unchanged. The post-validator's
source identity is recorded separately; it is not a rerun of native generation.
After a diagnosed validation-code repair, a new invocation may specify
`--post-report-name post-validation-v2.json`; the prior failure record stays
intact. Only a new filename matching `post-validation[-suffix].json` is accepted.
Input and copied-source maps must be complete and unchanged; both reference
native stages and all three rebuild native stages must have completed with
exit zero. Current XSA and SDT identities must match their original native
records. Project resources, original RTL, all saved BDs, all XCI component and
model parameter values, HWH module attributes/parameters/memory ranges, and
the BD-to-HWH GPIO master/address/range are checked.
The observed `counter32_0` module-reference XCI has no model-parameter section;
only that identified reference may treat the absent section as empty. Required
component-parameter sections and the vendor IP model sections must be present.

Only the observed native explicit addition of
`zynq_ultra_ps_e_0/PSU_MIO_22_INPUT_TYPE=cmos` can be explained by this narrow
post-validator. It requires complete B/C effective XCI and HWH equality and
matching values for that exact parameter. Its raw BD difference remains in the
report. Catalog default `NA` alone is not accepted as evidence. Any other raw
difference or changed effective value fails. Native `ImportPath` and
`ImportTime` are retained as provenance; actual file references still control
the inputs. The importer never follows those provenance hints to update an
external source file.

Pre-execution unsupported inputs return 2. A rejection after native execution
has begun is an execution failure and returns 1. Earlier preserved records
retain the real exit code produced by the source version that ran. Separate
BD/XSA/SDT cross-artifact verification remains required.
