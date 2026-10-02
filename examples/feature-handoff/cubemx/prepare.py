#!/usr/bin/env python3
"""Prepare an original idle CubeMX baseline and native evidence, never the feature.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
Uses the unchanged narrow adapter helpers for installed-tool and native-build checks.
No install, download, hardware, debugger, serial or Git operation is provided.
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
REPO = HERE.parents[2]
ADAPTER = REPO / "skills/embedded-project-workflow/scripts/cubemx_rtos.py"
spec = importlib.util.spec_from_file_location("cubemx_rtos", ADAPTER)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
NAME = "sample_statistics"
USER_SOURCES = ("Services/Sampling/sample_feed.c", "Domain/Statistics/statistics_worker.c")


def source_hashes():
    inputs = [HERE / (NAME + ".ioc"), HERE / "prepare.py"]
    inputs += sorted((HERE / "Services").rglob("*")) + sorted((HERE / "Domain").rglob("*"))
    return {p.relative_to(HERE).as_posix(): adapter.sha(p) for p in inputs if p.is_file()}


def outside_user_regions(body):
    return re.sub(r"(/\* USER CODE BEGIN (\w+) \*/).*?(/\* USER CODE END \2 \*/)",
                  r"\1\3", body, flags=re.S)


def add_user_files(uvprojx):
    tree = ET.parse(uvprojx)
    target = tree.getroot().find(".//Target")
    adapter.check_hooks(target)
    for parent, key, value in ((target, "pCCUsed", r"5060960::V5.06 update 7 (build 960)::.\ARMCC"),
                               (target, "uAC6", "0"),
                               (target.find(".//TargetCommonOption"), "PackID", adapter.PROFILE["pack"])):
        node = parent.find(key)
        if node is None:
            node = ET.SubElement(parent, key)
        node.text = value
    # CubeMX emits empty optional hooks; no generated/user program is executed.
    for flag in target.findall(".//RunUserProg1") + target.findall(".//RunUserProg2"):
        flag.text = "0"
    inc = target.find(".//Cads/VariousControls/IncludePath")
    inc.text = (inc.text or "") + ";../Services/Sampling;../Domain/Statistics"
    for folder, source in (("Services/Sampling", "sample_feed.c"), ("Domain/Statistics", "statistics_worker.c")):
        group = ET.SubElement(target.find("Groups"), "Group")
        ET.SubElement(group, "GroupName").text = folder
        files = ET.SubElement(group, "Files")
        file = ET.SubElement(files, "File")
        for key, value in (("FileName", source), ("FileType", "1"), ("FilePath", "../" + folder + "/" + source)):
            ET.SubElement(file, key).text = value
    tree.write(uvprojx, encoding="utf-8", xml_declaration=True)


def establish(args):
    work, reports = args.work_root.resolve(), args.reports.resolve()
    for label, path in (("work root", work), ("reports", reports)):
        adapter.reject_links(path)
        adapter.require(not adapter.inside(path, REPO), f"{label} must be outside source repository")
        adapter.require(not path.exists(), f"Use a new {label}")
    adapter.require(not adapter.inside(work, reports) and not adapter.inside(reports, work),
                    "Work and report directories must be separate")
    installation = adapter.doctor(adapter.tool_args(args))
    paths = installation["paths"]
    inputs_before, adapter_before = source_hashes(), adapter.sha(ADAPTER)
    original_model = adapter.parse_ioc((HERE / (NAME + ".ioc")).read_bytes())
    work.mkdir(parents=True)
    reports.mkdir(parents=True)
    project = work / NAME
    project.mkdir()
    ioc = project / (NAME + ".ioc")
    shutil.copy2(HERE / ioc.name, ioc)
    adapter.write_json(reports / "source-input-sha256.json", inputs_before)
    adapter.write_json(reports / "installation.json", installation)
    shutil.copy2(ioc, reports / "input.ioc")
    env = os.environ.copy()
    for key in adapter.FORBIDDEN_ENV:
        env.pop(key, None)
    temporary = reports / "tmp"
    temporary.mkdir()
    env.update(TEMP=str(temporary), TMP=str(temporary), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    commands = reports / "generation.mxscript"
    commands.write_text("\n".join([f'config load "{ioc.as_posix()}"', 'project toolchain "MDK-ARM V5.27"',
        f'project setCustomFWPath "{Path(paths["firmware"]).as_posix()}"', "project generate", "exit", ""]), encoding="utf-8")
    outcome = {"status": "STARTED", "stage": "native-generation", "project": str(project),
               "adapter_sha256": adapter_before, "source_inputs": inputs_before,
               "runtime": "NOT_RUN", "board": "NOT_RUN", "feature": "NOT_IMPLEMENTED"}
    journal = []

    def record(stage, **facts):
        journal.append({"stage": stage, "time_ns": time.time_ns(), **facts})
        adapter.write_json(reports / "journal.json", journal)
        outcome["stage"] = stage
        adapter.write_json(reports / "result.json", outcome)

    record("native-generation")
    try:
        started = time.time_ns()
        generated = project / "Core/Src/app_freertos.c"
        uvprojx = project / "MDK-ARM" / (NAME + ".uvprojx")
        generation = adapter.run([str(Path(paths["cubemx"]).parent / "jre/bin/java.exe"),
            "--add-opens", "java.desktop/java.awt=ALL-UNNAMED", "--add-exports", "java.desktop/sun.awt=ALL-UNNAMED",
            "-Dfile.encoding=UTF-8", "-jar", paths["cubemx"], "-q", str(commands)],
            project, reports / "cubemx.log", env)
        outcome["generation"] = generation
        adapter.check_generation(generation, reports / "cubemx.log", [generated, project / "Core/Src/main.c", uvprojx], started, None)
        adapter.write_json(reports / "native-generated-sha256.json", adapter.compilation_inputs(project))
        shutil.copy2(generated, reports / "native-generated-app_freertos.c")
        record("user-integration", generation_exit_code=generation["exit_code"])
        shutil.copytree(HERE / "Services", project / "Services")
        shutil.copytree(HERE / "Domain", project / "Domain")
        for name in ("PROJECT.md", "STATE.md"):
            shutil.copy2(HERE / name, project / name)
        native_body = generated.read_text(encoding="utf-8")
        body = native_body
        for region, addition in (("Includes", '\n#include "sample_feed.h"'),
                                 ("RTOS_THREADS", "\n  Sampling_CheckCreated();")):
            marker = f"/* USER CODE BEGIN {region} */"
            adapter.require(body.count(marker) == 1, f"Missing generated user region: {region}")
            body = body.replace(marker, marker + addition)
        adapter.require(outside_user_regions(native_body) == outside_user_regions(body), "Changed generator-owned code")
        generated.write_text(body, encoding="utf-8")
        creation_order = re.findall(r"\b(\w+Handle)\s*=\s*(?:osThreadNew|osMessageQueueNew)\s*\(", body)
        adapter.require(creation_order == ["SampleQueueHandle", "SampleFeedHandle", "StatsWorkerHandle"],
                        f"Unexpected native creation order: {creation_order}")
        adapter.require(body.index("Sampling_CheckCreated();") > body.index("StatsWorkerHandle = osThreadNew"),
                        "Handle checks must follow native creations")
        add_user_files(uvprojx)
        users = [project / p for p in USER_SOURCES]
        state = adapter.inspect_project(project, ioc, uvprojx, NAME, users, adapter.vendor_roots(paths))
        adapter.require(state["model"]["tasks"] == original_model["tasks"] and state["model"]["queues"] == original_model["queues"],
                        "Generation changed original object contract")
        receipt = {"project": str(project), "ioc": str(ioc), "uvprojx": str(uvprojx), "target": NAME,
                   "after": state["model"], "installation": installation, "owners": state["owners"],
                   "user_sources": state["user_sources"], "user_hashes": adapter.user_hashes(project, state["user_sources"]),
                   "user_regions": adapter.user_regions(project), "plan_id": "feature-handoff-idle-baseline"}
        adapter.write_json(reports / "baseline-receipt.json", receipt)
        # Keil owns this RTE header and rewrites it on the first cold rebuild.
        # Archive that bootstrap separately, then bind the final stable rebuild.
        rte_name = "MDK-ARM/RTE/_" + NAME + "/RTE_Components.h"
        rte_header = project / rte_name
        bootstrap_inputs = adapter.compilation_inputs(project, state["extra_inputs"])
        adapter.write_json(reports / "bootstrap-inputs-before.json", bootstrap_inputs)
        if rte_header.exists():
            shutil.copy2(rte_header, reports / "bootstrap-RTE-before.h")
        record("native-bootstrap-rebuild", creation_order=creation_order, user_entry_owners=state["owners"])
        started = time.time_ns()
        bootstrap = adapter.run([paths["uv4"], "-r", str(uvprojx), "-t", NAME, "-o", str(reports / "keil-bootstrap.log")],
                                uvprojx.parent, reports / "keil-bootstrap-process.log", env)
        outcome["bootstrap_build"] = bootstrap
        map_path = Path(state["outputs"]["ListingPath"]) / (NAME + ".map")
        image = Path(state["outputs"]["OutputDirectory"]) / (NAME + ".axf")
        bootstrap.update(adapter.check_build(bootstrap, reports / "keil-bootstrap.log", map_path, image, started))
        adapter.check_user_compilation(reports / "keil-bootstrap.log", state["user_sources"])
        compiled_before = adapter.compilation_inputs(project, state["extra_inputs"])
        adapter.write_json(reports / "bootstrap-inputs-after.json", compiled_before)
        changed = sorted(k for k in set(bootstrap_inputs) | set(compiled_before)
                         if bootstrap_inputs.get(k) != compiled_before.get(k))
        adapter.require(set(changed) <= {rte_name}, f"Unexpected source drift during native bootstrap: {changed}")
        if rte_header.exists():
            shutil.copy2(rte_header, reports / "bootstrap-RTE-after.h")
        outcome["bootstrap_native_generated_changes"] = changed
        adapter.write_json(reports / "build-inputs-before.json", compiled_before)
        record("native-rebuild", bootstrap_native_generated_changes=changed)
        started = time.time_ns()
        build = adapter.run([paths["uv4"], "-r", str(uvprojx), "-t", NAME, "-o", str(reports / "keil.log")],
                            uvprojx.parent, reports / "keil-process.log", env)
        outcome["build"] = build
        build.update(adapter.check_build(build, reports / "keil.log", map_path, image, started))
        adapter.check_user_compilation(reports / "keil.log", state["user_sources"])
        compiled_after = adapter.check_compilation_inputs(project, compiled_before)
        adapter.write_json(reports / "build-inputs-after.json", compiled_after)
        verified = adapter.verify_outputs(receipt, map_path)
        adapter.require(inputs_before == source_hashes(), "Original fixture inputs changed during preparation")
        adapter.require(adapter_before == adapter.sha(ADAPTER), "Adapter changed during preparation")
        products = reports / "products"
        products.mkdir()
        for product in (map_path, image):
            shutil.copy2(product, products / product.name)
        outcome.update(status="PASS", verification=verified, native_creation_order=creation_order,
                       generator_owned_code_preserved=True, compilation_input_count=len(compiled_before),
                       ioc=str(ioc), uvprojx=str(uvprojx), user_sources=[str(p) for p in users],
                       products={p.suffix[1:]: {"path": str(p), "sha256": adapter.sha(p),
                                              "evidence_copy": str(products / p.name)} for p in (map_path, image)})
        adapter.write_json(reports / "project-after-build-sha256.json", adapter.snapshot(project))
        record("ready-for-handoff", errors=build["errors"], warnings=build["warnings"], feature="NOT_IMPLEMENTED")
    except BaseException as exc:
        outcome.update(status="FAILED", error=str(exc), error_type=type(exc).__name__)
        raise
    finally:
        adapter.write_json(reports / "result.json", outcome)
    print(str(reports / "result.json"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    adapter.add_tools(parser)
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
