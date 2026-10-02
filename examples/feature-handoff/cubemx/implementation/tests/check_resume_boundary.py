#!/usr/bin/env python3
"""Host-only regression for current-project preflight; no vendor process launches.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
Use a native feature project and a NEW output directory outside the repository.
"""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import shutil
from unittest.mock import patch
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("feature_boundary_test", HERE.parent / "apply.py")
feature = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feature)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--installation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    native, output = args.project.resolve(), args.output.resolve()
    feature.adapter.require(not output.exists(), "Use a new test output directory")
    feature.adapter.require(not feature.adapter.inside(output, feature.REPO) and
                            not feature.adapter.inside(output, native) and
                            not feature.adapter.inside(output, args.baseline), "Test output overlaps inputs")
    feature.adapter.reject_links(output)
    installation = json.loads(args.installation.read_text(encoding="utf-8"))
    output.mkdir(parents=True)
    work = output / "work"
    project = work / feature.NAME
    shutil.copytree(native, project, ignore=shutil.ignore_patterns("*.axf", "*.map", "*.o", "*.d", "*.crf", "*.htm", "*.hex"))
    uvprojx = project / "MDK-ARM" / (feature.NAME + ".uvprojx")
    tree = ET.parse(uvprojx)
    # Relocate only explicit external compiler inputs; generator-owned metadata
    # remains unchanged and is required to resolve within the copied project.
    for node in tree.findall(".//Files/File/FilePath"):
        path = (native / "MDK-ARM" / node.text.replace("\\", "/")).resolve()
        if not feature.adapter.inside(path, native):
            node.text = Path(os.path.relpath(path, uvprojx.parent)).as_posix()
    for node in tree.findall(".//IncludePath"):
        entries = []
        for raw in (node.text or "").split(";"):
            if not raw:
                continue
            path = (native / "MDK-ARM" / raw.replace("\\", "/")).resolve()
            destination = project / path.relative_to(native) if feature.adapter.inside(path, native) else path
            entries.append(Path(os.path.relpath(destination, uvprojx.parent)).as_posix())
        node.text = ";".join(entries)
    tree.write(uvprojx, encoding="utf-8", xml_declaration=True)
    mxproject = project / ".mxproject"
    ioc = project / (feature.NAME + ".ioc")
    originals = {p: p.read_bytes() for p in (uvprojx, mxproject, ioc)}
    outside = output / "outside-source.c"
    outside.write_text("/* External sentinel must remain unchanged. */\n", encoding="utf-8")
    outside_before = feature.adapter.sha(outside)
    business_before = {str(p): feature.adapter.sha(p) for p in [feature.CORE / "epw_stats.c", feature.CORE / "epw_stats.h"]}
    checks = []

    def options(name):
        return argparse.Namespace(baseline=args.baseline.resolve(), work_root=work, resume=True,
                                  reports=output / (name + "-reports"),
                                  **{key: Path(value) for key, value in installation["paths"].items()})

    def mutate_xml(expression, value):
        current = ET.parse(uvprojx)
        node = current.find(expression)
        assert node is not None, expression
        node.text = value
        current.write(uvprojx, encoding="utf-8", xml_declaration=True)

    def mutate_ioc(key, value):
        text = ioc.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert sum(line.startswith(key + "=") for line in lines) == 1
        ioc.write_text("\n".join(key + "=" + value if line.startswith(key + "=") else line for line in lines) + "\n", encoding="utf-8")

    def mutate_mx(value):
        text = mxproject.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert sum(line.startswith("SourceFiles#0=") for line in lines) == 1
        mxproject.write_text("\n".join("SourceFiles#0=" + value if line.startswith("SourceFiles#0=") else line for line in lines) + "\n", encoding="utf-8")

    def reject(name, mutate, reason):
        for path, data in originals.items():
            path.write_bytes(data)
        mutate()
        before = feature.adapter.snapshot(project)
        opts = options(name)
        caught = None
        with patch.object(feature, "integrate_build", side_effect=AssertionError("Project mutation reached")), \
             patch.object(feature.adapter, "doctor", side_effect=AssertionError("Native tool probe reached")), \
             patch.object(feature.adapter, "run", side_effect=AssertionError("Native dispatch reached")), \
             patch.object(feature.adapter.subprocess, "Popen", side_effect=AssertionError("Native process reached")):
            try:
                feature.establish(opts)
            except feature.adapter.AdapterError as error:
                caught = str(error)
        assert caught is not None and reason in caught, (name, caught, reason)
        assert feature.adapter.snapshot(project) == before, "Preflight rejection mutated project"
        assert not opts.reports.exists(), "Preflight rejection created reports before validation"
        assert feature.adapter.sha(outside) == outside_before
        checks.append({"case": name, "status": "PASS", "rejection": caught,
                       "project_unchanged": True, "native_dispatches": 0})

    reject("mx-deletion-outside", lambda: mutate_mx(str(outside)), ".mxproject generated/deletion path escapes")
    reject("mx-core-not-generator-owned", lambda: mutate_mx(str(feature.CORE / "epw_stats.c")), ".mxproject generated/deletion path escapes")
    reject("source-outside", lambda: mutate_xml(".//Files/File/FilePath", str(outside)), "project source escapes")
    reject("include-outside", lambda: mutate_xml(".//IncludePath", str(output)), "include directory escapes")
    reject("scatter-outside", lambda: mutate_xml(".//ScatterFile", str(outside)), "ScatterFile escapes")
    reject("output-outside", lambda: mutate_xml(".//OutputDirectory", str(output)), "OutputDirectory escapes")
    reject("listing-outside", lambda: mutate_xml(".//ListingPath", str(output)), "ListingPath escapes")
    reject("main-location-outside", lambda: mutate_ioc("ProjectManager.MainLocation", str(output)), "ProjectManager.MainLocation escapes")
    reject("ioc-hook", lambda: mutate_ioc("ProjectManager.UAScriptBeforePath", str(outside)), "CubeMX user hook is forbidden")
    reject("compiler-extra-flags", lambda: mutate_xml(".//MiscControls", "--via outside.rsp"), "Nonempty custom MiscControls")
    reject("unknown-metadata-key", lambda: mxproject.write_text(mxproject.read_text(encoding="utf-8") + "\nUnrecognizedFiles=outside.c\n", encoding="utf-8"), "Unsupported .mxproject key")
    for path, data in originals.items():
        path.write_bytes(data)
    accepted = feature.inspect_build(project, uvprojx)
    assert accepted["external_sources"] == [str(feature.CORE / "epw_stats.c")]
    assert set(accepted["external_inputs"]) == set(business_before)
    calls = []

    class Intercepted(RuntimeError):
        pass

    def intercept(command, cwd, *unused):
        calls.append({"command": [str(item) for item in command], "cwd": str(cwd)})
        raise Intercepted("Valid resume reached intercepted generation; no vendor launched")

    with patch.object(feature.adapter, "doctor", return_value=installation), \
         patch.object(feature.adapter, "run", side_effect=intercept), \
         patch.object(feature.adapter.subprocess, "Popen", side_effect=AssertionError("Native process reached")):
        try:
            feature.establish(options("valid-resume"))
        except Intercepted:
            pass
    assert len(calls) == 1
    assert feature.adapter.sha(outside) == outside_before
    assert all(feature.adapter.sha(Path(path)) == digest for path, digest in business_before.items())
    checks.append({"case": "valid-resume", "status": "PASS", "intercepted_dispatches": calls, "native_processes": 0})
    result = {"status": "PASS", "scope": "HOST_ONLY_PRELAUNCH_BOUNDARY_REGRESSION", "checks": checks,
              "source_sha256": {str(p): feature.adapter.sha(p) for p in (HERE / "check_resume_boundary.py", HERE.parent / "apply.py", feature.ADAPTER)},
              "shared_core_unchanged": True, "outside_file_unchanged": True, "native_processes": 0}
    feature.adapter.write_json(output / "result.json", result)
    print(json.dumps({"status": "PASS", "rejected_cases": len(checks) - 1, "valid_resume_accepted": True, "native_processes": 0}))


if __name__ == "__main__":
    main()
