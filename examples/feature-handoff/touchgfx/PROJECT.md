# Existing-project feature handoff: CounterHandoff

## Baseline and ownership

The supplied original source defines Dashboard and Controls in native TouchGFX
4.26.1 `.touchgfx` format, Simulator application template 2.0.0, 480 x 272,
RGB565. Dashboard shows count and pause state. Native navigation opens Controls
and returns to Dashboard. Controls Pause / Resume calls the preserved user View,
Presenter and Model. The model increments every 60 unpaused GUI ticks, saturates
at 999999, and retains count, pause state and partial period across navigation.
GUI ticks are not a measured wall clock.

`CounterHandoff.touchgfx` owns layout, page identities and native interactions;
`texts.xml` owns text, typography and wildcard glyph declarations. `user/gui`
contains the original user implementation. `generated/gui_generated` belongs to
the native generator and must never be manually patched. The package contains no
vendor template, library, font, generated source, binary or tool log.

## Reproduce a fresh baseline

Use the installed tools; no download or installation is needed. `setup.py` only
prepares this initial original fixture in a brand-new destination. It does not
support takeover and is never used again after that first preparation.

```powershell
python setup.py --touchgfx-root "<TouchGFX安装目录>" --destination "<新双页工程目录>" --reports "<新准备报告目录>"
python ../../../skills/embedded-project-workflow/scripts/touchgfx_project.py inspect --project "<新双页工程目录>" --touchgfx-root "<TouchGFX安装目录>"
python ../../../skills/embedded-project-workflow/scripts/touchgfx_project.py build --project "<新双页工程目录>" --touchgfx-root "<TouchGFX安装目录>" --reports "<新基线报告目录>"
```

The existing-project runner accepts inspect / generate / build. Inspect is
read-only and invokes no native tool. Build includes fresh generation and a
clean Simulator build. Each mutating invocation requires a new reports folder
outside the project and installation. Earlier generated/build trees are moved
there for evidence; source files are neither restored from this package nor
overwritten. Reports include input identities, logs, actual exit codes and
source preservation checks. Scope is the unmodified native Simulator GCC build
profile and RGB565; custom hooks, modified build makefiles, framework modifications,
external resource paths and filesystem links are rejected. Build is not GUI or
hardware validation. Close/save any concurrent Designer writer before generation.

## Next feature brief (not implemented in baseline)

Take over the existing prepared project through its current native configuration.
Add a native Statistics page and native Controls navigation to it and back.
Keep Dashboard, Controls, dimensions, format, counter cadence, count and pause
semantics. Statistics displays count, retained sample count, rolling minimum,
maximum and average over the latest eight counter samples. Append a sample only
when the counter actually increments. Keep statistics computation in a separate
original core module with a clear model/presenter interface, meaningful host tests
and an injected defect negative control. No Statistics page or core is supplied
in this baseline.

Reserve the Statistics rectangle x=260..460, y=132..180 for a later HUMAN Reset
button, including a native ActionCustom callback. Do not add a Reset button or
Reset implementation during the first feature handoff. The later human edit
must remain visible in the native source and survive the resumed generation.
The earlier preparation notes said Controls here; that was a page-name typo.
The requested later human edit belongs to Statistics, not a changed user contract.
Do not recreate the application, replace Screens from a fixed fixture, copy the
baseline gui over current user code, or hand-write generated base classes.

Acceptance distinguishes native generation/build, host core behavior, actual
simulator interaction, and target hardware. Only claim the evidence obtained.
