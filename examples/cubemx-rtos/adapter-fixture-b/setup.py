#!/usr/bin/env python3
"""Establish an original A or B baseline by native generation and rebuild only.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
This creates fixture data for the adapter; it is not part of adapter plan/apply.
No flashing, debugger, serial, installation, or download operation is provided.
"""
from pathlib import Path
import argparse
import importlib.util
import os
import shutil
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ADAPTER = REPO / "skills/embedded-project-workflow/scripts/cubemx_rtos.py"
spec = importlib.util.spec_from_file_location("cubemx_rtos", ADAPTER)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def establish(args):
    installation = adapter.doctor(adapter.tool_args(args))
    paths = installation["paths"]
    work = args.work_root.resolve()
    reports = args.reports.resolve()
    for label, path in (("work root", work), ("reports", reports)):
        adapter.require(not adapter.inside(path, REPO), f"{label} must be outside source repository")
        adapter.require(not path.exists(), f"Use a new {label}")
    adapter.require(not adapter.inside(work, reports) and not adapter.inside(reports, work), "Work and reports must be separate")
    if args.fixture == "a":
        source, name, folder = HERE.parent, "rtos_ownership", "APP"
        header, app, hook = "rtos_app.h", "rtos_app.c", "RtosApp_CheckCreated"
    else:
        source, name, folder = HERE, "telemetry_fixture", "Application/Telemetry"
        header, app, hook = "telemetry_tasks.h", "telemetry_tasks.c", "Telemetry_CheckCreated"
    work.mkdir(parents=True)
    reports.mkdir(parents=True)
    project = work / name
    project.mkdir()
    ioc = project / (name + ".ioc")
    shutil.copy2(source / (name + ".ioc"), ioc)
    adapter.parse_ioc(ioc.read_bytes())
    env = os.environ.copy()
    for key in adapter.FORBIDDEN_ENV:
        env.pop(key, None)
    temp = reports / "tmp"
    temp.mkdir()
    env.update(TEMP=str(temp), TMP=str(temp), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    script = reports / "initial.mxscript"
    script.write_text('\n'.join([f'config load "{ioc.as_posix()}"', 'project toolchain "MDK-ARM V5.27"',
        f'project setCustomFWPath "{Path(paths["firmware"]).as_posix()}"', 'project generate', 'exit', '']), encoding="utf-8")
    outcome = {"fixture": args.fixture, "project": str(project), "status": "STARTED", "runtime": "NOT_RUN"}
    adapter.write_json(reports / "result.json", outcome)
    try:
        start = time.time_ns()
        generated = project / "Core/Src/app_freertos.c"
        uvprojx = project / "MDK-ARM" / (name + ".uvprojx")
        generation = adapter.run([str(Path(paths["cubemx"]).parent / "jre/bin/java.exe"),
            "--add-opens", "java.desktop/java.awt=ALL-UNNAMED", "--add-exports", "java.desktop/sun.awt=ALL-UNNAMED",
            "-Dfile.encoding=UTF-8", "-jar", paths["cubemx"], "-q", str(script)], project, reports / "cubemx.log", env)
        adapter.check_generation(generation, reports / "cubemx.log", [generated, project / "Core/Src/main.c", uvprojx], start, None)
        shutil.copytree(source / folder, project / folder)
        body = generated.read_text(encoding="utf-8")
        for region, insert in (("Includes", f'\n#include "{header}"'), ("RTOS_THREADS", f"\n  {hook}();")):
            marker = f"/* USER CODE BEGIN {region} */"
            adapter.require(body.count(marker) == 1, f"Missing integration region: {region}")
            body = body.replace(marker, marker + insert)
        generated.write_text(body, encoding="utf-8")
        tree = ET.parse(uvprojx)
        target = tree.getroot().find(".//Target")
        adapter.check_hooks(target)
        for parent, key, value in ((target, "pCCUsed", r"5060960::V5.06 update 7 (build 960)::.\ARMCC"),
                                   (target, "uAC6", "0"), (target.find(".//TargetCommonOption"), "PackID", adapter.PROFILE["pack"])):
            node = parent.find(key)
            if node is None:
                node = ET.SubElement(parent, key)
            node.text = value
        for flag in target.findall(".//RunUserProg1") + target.findall(".//RunUserProg2"):
            flag.text = "0"
        inc = target.find(".//Cads/VariousControls/IncludePath")
        inc.text = (inc.text or "") + ";../" + folder
        group = ET.SubElement(target.find("Groups"), "Group")
        ET.SubElement(group, "GroupName").text = "Original user application"
        files = ET.SubElement(group, "Files")
        file = ET.SubElement(files, "File")
        for key, value in (("FileName", app), ("FileType", "1"), ("FilePath", "../" + folder + "/" + app)):
            ET.SubElement(file, key).text = value
        tree.write(uvprojx, encoding="utf-8", xml_declaration=True)
        state = adapter.inspect_project(project, ioc, uvprojx, name, [project / folder / app], adapter.vendor_roots(paths))
        # Baseline verification uses an unchanged IOC receipt only inside this setup tool.
        receipt = {"project": str(project), "ioc": str(ioc), "uvprojx": str(uvprojx), "target": name,
                   "after": state["model"], "installation": installation, "owners": state["owners"],
                   "user_sources": state["user_sources"], "user_hashes": adapter.user_hashes(project, state["user_sources"]),
                   "user_regions": adapter.user_regions(project), "plan_id": "fixture-baseline-" + args.fixture}
        start = time.time_ns()
        build = adapter.run([paths["uv4"], "-r", str(uvprojx), "-t", name, "-o", str(reports / "keil.log")],
                            uvprojx.parent, reports / "keil-process.log", env)
        map_path = Path(state["outputs"]["ListingPath"]) / (name + ".map")
        image_path = Path(state["outputs"]["OutputDirectory"]) / (name + ".axf")
        build.update(adapter.check_build(build, reports / "keil.log", map_path, image_path, start))
        adapter.check_user_compilation(reports / "keil.log", state["user_sources"])
        outcome.update(status="PASS", generation=generation, build=build, verification=adapter.verify_outputs(receipt, map_path),
                       ioc=str(ioc), uvprojx=str(uvprojx), target=name, user_source=str(project / folder / app))
    except BaseException as exc:
        outcome.update(status="FAILED", error=str(exc))
        raise
    finally:
        adapter.write_json(reports / "result.json", outcome)
    print(str(reports / "result.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    adapter.add_tools(parser)
    parser.add_argument("--fixture", choices=("a", "b"), required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--reports", type=Path, required=True)
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
