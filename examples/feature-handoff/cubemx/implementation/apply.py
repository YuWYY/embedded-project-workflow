#!/usr/bin/env python3
"""Apply this feature to a NEW copy of its native idle baseline, regenerate, rebuild.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
Project-specific external-core integration; does not broaden cubemx_rtos.py.
"""
from pathlib import Path
import argparse
import importlib.util
import os
import re
import shutil
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CORE = REPO / "examples/common/rolling-stats"
ADAPTER = REPO / "skills/embedded-project-workflow/scripts/cubemx_rtos.py"
spec = importlib.util.spec_from_file_location("cubemx_rtos", ADAPTER)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
NAME = "sample_statistics"
USER_SOURCES = ("Services/Sampling/sample_feed.c", "Domain/Statistics/statistics_worker.c")


def source_hashes():
    paths = [p for p in HERE.rglob("*") if p.is_file() and "__pycache__" not in p.parts]
    paths += [CORE / "epw_stats.c", CORE / "epw_stats.h", ADAPTER]
    return {p.relative_to(REPO).as_posix(): adapter.sha(p) for p in sorted(paths)}


def outside_user_regions(body):
    return re.sub(r"(/\* USER CODE BEGIN (\w+) \*/).*?(/\* USER CODE END \2 \*/)",
                  r"\1\3", body, flags=re.S)


def user_hashes(project):
    return {p.relative_to(project).as_posix(): adapter.sha(p)
            for folder in ("Services", "Domain") for p in sorted((project / folder).rglob("*")) if p.is_file()}


def integrate_build(uvprojx):
    tree = ET.parse(uvprojx)
    target = tree.getroot().find(".//Target")
    adapter.check_hooks(target)
    # The generated project already selects the installed baseline compiler.
    adapter.require(target.findtext("pCCUsed") == r"5060960::V5.06 update 7 (build 960)::.\ARMCC",
                    "Compiler selection changed; inspect the generated project")
    inc = target.find(".//Cads/VariousControls/IncludePath")
    includes = (inc.text or "").split(";")
    for path in (uvprojx.parent.parent / "Services/Sampling", uvprojx.parent.parent / "Domain/Statistics", CORE):
        relative = Path(os.path.relpath(path, uvprojx.parent)).as_posix()
        resolved = [(uvprojx.parent / p.replace("\\", "/")).resolve() for p in includes if p]
        if path.resolve() not in resolved:
            includes.append(relative)
    inc.text = ";".join(includes)
    core_path = CORE / "epw_stats.c"
    matching = [n for n in target.findall(".//Files/File")
                if (uvprojx.parent / n.findtext("FilePath").replace("\\", "/")).resolve() == core_path.resolve()]
    adapter.require(len(matching) <= 1, "Duplicate shared core compilation")
    if not matching:
        group = ET.SubElement(target.find("Groups"), "Group")
        ET.SubElement(group, "GroupName").text = "Common/RollingStatistics"
        file = ET.SubElement(ET.SubElement(group, "Files"), "File")
        for key, value in (("FileName", core_path.name), ("FileType", "1"),
                           ("FilePath", Path(os.path.relpath(core_path, uvprojx.parent)).as_posix())):
            ET.SubElement(file, key).text = value
    tree.write(uvprojx, encoding="utf-8", xml_declaration=True)


def inspect_build(project, uvprojx, require_core=True, expected_model=None):
    """Read-only preflight of the current project, including generator ownership.

    Only the named shared source/header may be external compilation inputs.
    Generator metadata, output and scatter paths never gain that exception.
    """
    project = adapter.checked_path(project, [project], "current project")
    uvprojx = adapter.checked_path(uvprojx, [project], "current uvprojx")
    ioc = adapter.checked_path(project / (NAME + ".ioc"), [project], "current IOC")
    adapter.checked_path(project / ".mxproject", [project], "current .mxproject")
    model = adapter.parse_ioc(ioc.read_bytes())
    adapter.inspect_mxproject(project, uvprojx.parent)
    adapter.resolve_uv(model["values"].get("ProjectManager.MainLocation", "Core/Src"),
                       project, [project], "ProjectManager.MainLocation", exists=False)
    adapter.require(model["values"].get("ProjectManager.ToolChainLocation", "") == "",
                    "Custom CubeMX toolchain location is unsupported")
    adapter.require(model["values"].get("ProjectManager.ProjectName") == uvprojx.stem and
                    model["values"].get("ProjectManager.ProjectFileName") == ioc.name,
                    "Current IOC/project identity mismatch")
    if expected_model is not None:
        adapter.require(model["tasks"] == expected_model["tasks"] and model["queues"] == expected_model["queues"],
                        "Current native object contract differs from the baseline")
    external_inputs = {str(adapter.checked_path(CORE / name, [CORE], "shared core dependency")): adapter.sha(CORE / name)
                       for name in ("epw_stats.c", "epw_stats.h")}
    root = adapter.read_xml(uvprojx)
    target = root.find(".//Target")
    adapter.require(root.findall(".//Target") == [target], "Expected one target")
    adapter.require(target.findtext("TargetName") == NAME, "Target changed")
    adapter.require(target.findtext("pCCUsed") == r"5060960::V5.06 update 7 (build 960)::.\ARMCC" and
                    target.findtext("uAC6") == "0", "Compiler changed")
    adapter.require(target.findtext(".//PackID") == adapter.PROFILE["pack"], "Device pack changed")
    adapter.require(target.findtext(".//Device", "").startswith("STM32G474RE"), "Device changed")
    adapter.check_hooks(target)
    sources = []
    for group in target.findall(".//Groups/Group"):
        adapter.require(group.findtext("./GroupOption/CommonProperty/IncludeInBuild", "1") != "0", "Excluded group")
        for node in group.findall("./Files/File"):
            path = adapter.resolve_uv(node.findtext("FilePath"), uvprojx.parent, [project, CORE], "project source")
            adapter.require(path.is_file(), f"Missing source: {path}")
            adapter.require(adapter.inside(path, project) or path == (CORE / "epw_stats.c").resolve(),
                            f"Unexpected external source: {path}")
            adapter.require(node.findtext(".//IncludeInBuild", "1") != "0", f"Excluded source: {path}")
            adapter.require(node.findtext("FileType") in ("1", "2", "5"), "Unexpected file action")
            sources.append(path)
    adapter.require(len(sources) == len(set(sources)), "Duplicate source reference")
    stems = [p.stem.lower() for p in sources if p.suffix.lower() in (".c", ".s", ".cpp")]
    adapter.require(len(stems) == len(set(stems)), "Ambiguous object basename")
    required_sources = [project / p for p in USER_SOURCES] + ([CORE / "epw_stats.c"] if require_core else [])
    for path in required_sources:
        adapter.require(sources.count(path.resolve()) == 1, f"Required source absent or duplicated: {path}")
    for node in target.findall(".//IncludePath"):
        for raw in (node.text or "").split(";"):
            if raw.strip():
                path = adapter.resolve_uv(raw.strip(), uvprojx.parent, [project, CORE], "include directory")
                adapter.require(path.is_dir() and (adapter.inside(path, project) or path == CORE.resolve()),
                                f"Unexpected include path: {path}")
    outputs = {}
    for tag in ("OutputDirectory", "ListingPath"):
        nodes = target.findall(".//" + tag)
        adapter.require(len(nodes) == 1, f"Expected one {tag}")
        outputs[tag] = str(adapter.resolve_uv(nodes[0].text, uvprojx.parent, [project], tag, exists=False))
    adapter.require(target.findtext(".//OutputName") == NAME, "Output name changed")
    extra_inputs = []
    for node in target.findall(".//ScatterFile"):
        if (node.text or "").strip():
            extra_inputs.append(str(adapter.resolve_uv(node.text, uvprojx.parent, [project], "ScatterFile")))
    for tag in ("MiscControls", "BinPath", "LibPath", "CustomArgument", "IncludeLibraryModules", "IncludeLibs",
                "IncludeLibsPath", "LinkerInputFile", "Misc", "pFcarmOut", "pFcarmGrp", "pFcArmRoot"):
        for node in target.findall(".//" + tag):
            adapter.require(not (node.text or "").strip(), f"Nonempty custom {tag} is unsupported")
    return {"sources": [str(p) for p in sources],
            "external_sources": [str(CORE / "epw_stats.c")],
            "external_include": str(CORE), "external_inputs": external_inputs,
            "extra_inputs": extra_inputs, "outputs": outputs}


def inputs(project, extra_inputs=()):
    result = adapter.compilation_inputs(project, extra_inputs)
    for name in ("epw_stats.c", "epw_stats.h"):
        result["EXTERNAL:" + str(CORE / name)] = adapter.sha(CORE / name)
    return result


def check_regeneration(record, log, generated, uvprojx, started):
    # The native tool preserves the timestamp of an unchanged C output. This
    # feature does not edit the IOC, unlike the narrow adapter's stack operation.
    adapter.require(record.get("exit_code") == 0, "CubeMX process failed")
    body = log.read_text(encoding="utf-8", errors="replace")
    adapter.require(not re.search(r"Exception|Code generation failed|FileNotFound|generation.*(?:failed|error)", body, re.I),
                    "CubeMX log reports a generation failure")
    adapter.require("Generated code: " + str(generated) in body and re.search(r"(?m)^OK\s*$", body),
                    "Missing native generated-output or completion log")
    for p in (generated, generated.parent / "main.c", uvprojx):
        adapter.require(p.is_file() and p.stat().st_size > 0, f"Missing native output: {p}")
    adapter.require(uvprojx.stat().st_mtime_ns >= started - 2_000_000_000, "Stale generated project file")


def establish(args):
    for path in (args.baseline, args.work_root, args.reports):
        adapter.reject_links(path)
    baseline = args.baseline.resolve()
    work, reports = args.work_root.resolve(), args.reports.resolve()
    adapter.require(baseline.is_dir(), "Native idle baseline is required")
    for path in (work, reports):
        adapter.reject_links(path)
        adapter.require(not path.exists() or (args.resume and path == work), f"Use a new destination: {path}")
        adapter.require(not adapter.inside(path, REPO) and not adapter.inside(path, baseline), "Destination overlaps source")
    adapter.require(not adapter.inside(work, reports) and not adapter.inside(reports, work), "Work/reports overlap")
    original = adapter.snapshot(baseline)
    source_before = source_hashes()
    baseline_state = adapter.inspect_project(baseline, baseline / (NAME + ".ioc"),
        baseline / "MDK-ARM" / (NAME + ".uvprojx"), NAME,
        [baseline / p for p in USER_SOURCES])
    project = work / NAME
    current_preflight = None
    if args.resume:
        adapter.require(project.is_dir(), "Resume requires the existing feature project")
        # This must precede all project writes and any native tool execution.
        current_preflight = inspect_build(project, project / "MDK-ARM" / (NAME + ".uvprojx"),
                                          expected_model=baseline_state["model"])
        for folder in ("Services", "Domain"):
            for source in (HERE / folder).rglob("*"):
                if source.is_file():
                    destination = project / source.relative_to(HERE)
                    adapter.require(destination.is_file() and adapter.sha(source) == adapter.sha(destination),
                                    f"Resume does not overwrite differing feature source: {destination}")
    installation = adapter.doctor(adapter.tool_args(args))
    paths = installation["paths"]
    work.mkdir(parents=True, exist_ok=args.resume)
    reports.mkdir(parents=True)
    if not args.resume:
        shutil.copytree(baseline, project)
    adapter.write_json(reports / "baseline-sha256.json", original)
    adapter.write_json(reports / "source-input-sha256.json", source_before)
    adapter.write_json(reports / "installation.json", installation)
    if current_preflight is not None:
        adapter.write_json(reports / "resume-preflight.json", current_preflight)
    outcome = {"status": "STARTED", "stage": "feature-integration", "baseline": str(baseline),
               "project": str(project), "resume": args.resume, "runtime": "NOT_RUN", "board": "NOT_RUN"}
    journal = []

    def record(stage, **facts):
        journal.append({"stage": stage, "time_ns": time.time_ns(), **facts})
        adapter.write_json(reports / "journal.json", journal)
        outcome["stage"] = stage
        adapter.write_json(reports / "result.json", outcome)

    record("feature-integration")
    try:
        uvprojx = project / "MDK-ARM" / (NAME + ".uvprojx")
        ioc = project / (NAME + ".ioc")
        # Also guard a newly copied project before replacing its idle user code.
        preflight = inspect_build(project, uvprojx, require_core=args.resume, expected_model=baseline_state["model"])
        adapter.require(current_preflight is None or current_preflight == preflight,
                        "Resumed project or shared dependencies changed after initial preflight")
        if not args.resume:
            for folder in ("Services", "Domain"):
                shutil.copytree(HERE / folder, project / folder, dirs_exist_ok=True)
        integrate_build(uvprojx)
        linked_before = inspect_build(project, uvprojx, expected_model=baseline_state["model"])
        adapter.require(linked_before["external_inputs"] == preflight["external_inputs"], "Shared core changed after preflight")
        users_before = user_hashes(project)
        regions_before = adapter.user_regions(project)
        # Non-user bodies preserve initialization, IRQ and native RTOS objects.
        protected = [p for p in (project / "Core").rglob("*") if p.suffix.lower() in (".c", ".h")]
        generated_before = {p.relative_to(project).as_posix(): outside_user_regions(p.read_text(encoding="utf-8-sig")) for p in protected}
        shutil.copy2(uvprojx, reports / "before-regeneration.uvprojx")
        adapter.write_json(reports / "pre-generation-inputs.json", inputs(project, linked_before["extra_inputs"]))
        commands = reports / "generation.mxscript"
        commands.write_text("\n".join([f'config load "{ioc.as_posix()}"', 'project toolchain "MDK-ARM V5.27"',
            f'project setCustomFWPath "{Path(paths["firmware"]).as_posix()}"', "project generate", "exit", ""]), encoding="utf-8")
        env = os.environ.copy()
        for key in adapter.FORBIDDEN_ENV:
            env.pop(key, None)
        temporary = reports / "tmp"
        temporary.mkdir()
        env.update(TEMP=str(temporary), TMP=str(temporary), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        record("native-regeneration")
        adapter.require(inspect_build(project, uvprojx, expected_model=baseline_state["model"]) == linked_before,
                        "Current project boundaries or shared core changed before dispatch")
        started = time.time_ns()
        generation = adapter.run([str(Path(paths["cubemx"]).parent / "jre/bin/java.exe"),
            "--add-opens", "java.desktop/java.awt=ALL-UNNAMED", "--add-exports", "java.desktop/sun.awt=ALL-UNNAMED",
            "-Dfile.encoding=UTF-8", "-jar", paths["cubemx"], "-q", str(commands)],
            project, reports / "cubemx.log", env)
        outcome["generation"] = generation
        generated = project / "Core/Src/app_freertos.c"
        check_regeneration(generation, reports / "cubemx.log", generated, uvprojx, started)
        shutil.copy2(uvprojx, reports / "native-regenerated.uvprojx")
        adapter.require(user_hashes(project) == users_before, "Regeneration changed feature sources")
        adapter.require(adapter.user_regions(project) == regions_before, "Regeneration changed user regions")
        for name, body in generated_before.items():
            adapter.require(outside_user_regions((project / name).read_text(encoding="utf-8-sig")) == body,
                            f"Regeneration changed generator-owned code: {name}")
        model = adapter.parse_ioc(ioc.read_bytes())
        adapter.require(model["tasks"] == baseline_state["model"]["tasks"] and
                        model["queues"] == baseline_state["model"]["queues"], "Native object contract changed")
        linked_after = inspect_build(project, uvprojx, expected_model=baseline_state["model"])
        adapter.require(linked_after == linked_before, "Regeneration changed source/include bindings")
        adapter.write_json(reports / "linked-sources.json", linked_after)
        native = adapter.strip_c_comments(generated.read_text(encoding="utf-8-sig"))
        order = re.findall(r"\b(\w+Handle)\s*=\s*(?:osThreadNew|osMessageQueueNew)\s*\(", native)
        adapter.require(order == ["SampleQueueHandle", "SampleFeedHandle", "StatsWorkerHandle"], "Native creation order changed")
        adapter.require(native.index("Sampling_CheckCreated();") > native.index("StatsWorkerHandle = osThreadNew"), "Creation guard moved")
        before = inputs(project, linked_after["extra_inputs"])
        adapter.write_json(reports / "build-inputs-before.json", before)
        record("native-rebuild", source_bindings_preserved=True, user_regions_preserved=True, native_creation_order=order)
        started = time.time_ns()
        build = adapter.run([paths["uv4"], "-r", str(uvprojx), "-t", NAME, "-o", str(reports / "keil.log")],
                            uvprojx.parent, reports / "keil-process.log", env)
        outcome["build"] = build
        map_path = Path(linked_after["outputs"]["ListingPath"]) / (NAME + ".map")
        image = Path(linked_after["outputs"]["OutputDirectory"]) / (NAME + ".axf")
        build.update(adapter.check_build(build, reports / "keil.log", map_path, image, started))
        adapter.check_user_compilation(reports / "keil.log", [project / p for p in USER_SOURCES] + [CORE / "epw_stats.c"])
        after = inputs(project, linked_after["extra_inputs"])
        adapter.write_json(reports / "build-inputs-after.json", after)
        adapter.require(before == after, "Compilation inputs changed during native rebuild")
        map_text = map_path.read_text(encoding="utf-8", errors="replace")
        owners = {"SampleFeed_Entry": "sample_feed.o", "StatsWorker_Entry": "statistics_worker.o",
                  "epw_stats_init": "epw_stats.o", "epw_stats_push": "epw_stats.o", "epw_stats_read": "epw_stats.o"}
        for symbol, owner in owners.items():
            found = re.findall(r"^\s*" + re.escape(symbol) + r"\s+0x[0-9a-fA-F]+\s+Thumb Code\s+\d+\s+([^\r\n]+)", map_text, re.M)
            adapter.require(len(found) == 1 and re.match(re.escape(owner) + r"(?:\(|\s|$)", found[0], re.I),
                            f"Unexpected linked owner for {symbol}: {found}")
        adapter.map_size(map_text, "SampleFeedStack", 1024)
        adapter.map_size(map_text, "SampleQueueStorage", 48)
        adapter.require(adapter.snapshot(baseline) == original, "Original native baseline changed")
        adapter.require(source_hashes() == source_before, "Feature source changed during validation")
        products = reports / "products"
        products.mkdir()
        for p in (map_path, image):
            shutil.copy2(p, products / p.name)
        outcome.update(status="PASS", linked_owners=owners, generator_owned_code_preserved=True,
                       user_regions_preserved=True, native_creation_order=order, source_bindings_preserved=True,
                       compilation_inputs_stable=True, baseline_preserved=True,
                       static_storage_map_bytes={"SampleFeedStack": 1024, "SampleQueueStorage": 48},
                       products={p.name: {"sha256": adapter.sha(p), "path": str(products / p.name)} for p in (map_path, image)})
        adapter.write_json(reports / "project-after-build-sha256.json", adapter.snapshot(project))
        record("complete", errors=build["errors"], warnings=build["warnings"])
    except BaseException as exc:
        outcome.update(status="FAILED", error=str(exc), error_type=type(exc).__name__)
        raise
    finally:
        adapter.write_json(reports / "result.json", outcome)
    print(str(reports / "result.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    adapter.add_tools(parser)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
    parser.add_argument("--resume", action="store_true", help="Validate an existing feature work copy with a NEW reports directory; do not recopy user sources")
    args = parser.parse_args()
    try:
        establish(args)
        return 0
    except KeyboardInterrupt:
        return 130
    except (adapter.AdapterError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
