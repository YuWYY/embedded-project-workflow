"""Run five isolated Vivado experiments; requires Windows and Vivado 2025.1.

Original RTL and scripts are copied into a new ASCII build directory. No board
connection, implementation, bitstream generation, or existing project is used.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes(package):
    return {
        path.relative_to(package).as_posix(): digest(path)
        for folder in ("sources", "scripts")
        for path in sorted((package / folder).rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def resolve_vivado(value):
    executable = value or shutil.which("vivado.bat") or shutil.which("vivado.exe")
    if not executable:
        raise ValueError("Vivado not found on PATH; provide --vivado <vivado.bat>.")
    executable = Path(executable).expanduser().resolve()
    if not executable.is_file():
        raise ValueError("The selected Vivado executable does not exist.")
    return executable


def create_build_root(value, package):
    root = Path(value).expanduser().resolve() if value else Path(
        tempfile.mkdtemp(prefix="embedded-workflow-vivado-")
    ).resolve()
    try:
        str(root).encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("Use --build-root with an empty ASCII path for Vivado.") from exc
    if root == package or package in root.parents:
        raise ValueError("Build root must be outside the example source directory.")
    if root.exists() and (not root.is_dir() or any(root.iterdir())):
        raise ValueError("Build root must be new or empty; existing work is preserved.")
    root.mkdir(parents=True, exist_ok=True)
    return root


def xci_semantics(work):
    candidates = list((work / "p").rglob("clkgen.xci"))
    if len(candidates) != 1:
        raise RuntimeError("Expected one Clocking Wizard configuration source.")
    data = json.loads(candidates[0].read_text(encoding="utf-8"))["ip_inst"]
    groups = ("component_parameters", "model_parameters", "project_parameters")
    return {
        "component_reference": data["component_reference"],
        "ip_revision": data["ip_revision"],
        "parameters": {
            group: {
                key: [item["value"] for item in values]
                for key, values in data["parameters"][group].items()
            }
            for group in groups
        },
    }


def read_result(work, filename):
    paths = list((work / "p").glob("*.sim/sim_1/behav/xsim/" + filename))
    if len(paths) != 1:
        raise RuntimeError("Expected one simulation result: " + filename)
    return paths[0].read_text(encoding="utf-8").strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vivado", help="Vivado executable; otherwise search PATH")
    parser.add_argument("--build-root", help="New or empty ASCII build directory")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("This entrypoint is currently validated only on Windows.")
    package = Path(__file__).resolve().parents[1]
    try:
        vivado = resolve_vivado(args.vivado)
        root = create_build_root(args.build_root, package)
    except ValueError as exc:
        parser.error(str(exc))
    print("Build directory:", root, flush=True)
    initial = source_hashes(package)
    shutil.copytree(package / "sources", root / "sources")
    shutil.copytree(package / "scripts", root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
    summary = {
        "status": "running",
        "platform": "Windows",
        "part": "xc7a200tfbg484-2",
        "source_sha256": initial,
        "stages": [],
        "coverage": "IP generation, XSim, synthesis; no implementation or hardware",
    }
    ledger = []

    def run(name, folder, script, script_args, completion, filename):
        work = root / folder
        work.mkdir(exist_ok=True)
        # Remove stale markers before regenerating an existing project.
        marker = work / "completed.txt"
        if marker.exists():
            marker.unlink()
        command = [str(vivado), "-mode", "batch", "-notrace", "-source",
                   str(root / "scripts" / script), "-tclargs",
                   str(root / "sources"), *script_args]
        start = time.monotonic()
        with (root / (name + ".stdout.log")).open("w", encoding="utf-8") as output:
            result = subprocess.run(command, cwd=work, stdout=output,
                                    stderr=subprocess.STDOUT, check=False)
        done = marker.read_text(encoding="utf-8").strip() if marker.exists() else ""
        unchanged = initial == source_hashes(package) == source_hashes(root)
        entry = {"name": name, "returncode": result.returncode,
                 "completion": done, "sources_unchanged": unchanged,
                 "elapsed_seconds": round(time.monotonic() - start, 2)}
        summary["stages"].append(entry)
        ledger.append({**entry, "command": command, "cwd": str(work)})
        write_json(root / "execution_ledger.json", ledger)
        write_json(root / "summary.json", summary)
        if result.returncode or completion not in done or not unchanged:
            raise RuntimeError(name + " failed; inspect its stdout log and project logs")
        entry["simulation"] = read_result(work, filename)
        version = (work / "tool_version.txt").read_text(encoding="utf-8").strip()
        if "vivado_version" in summary and summary["vivado_version"] != version:
            raise RuntimeError("Vivado version changed between stages")
        summary["vivado_version"] = version
        # Preserve the first clock stage before regeneration overwrites its reports.
        evidence = root / "stage-results" / name
        evidence.mkdir(parents=True)
        for report in work.glob("*.rpt"):
            shutil.copy2(report, evidence / report.name)
        for basename in ("ip_properties.txt", "completed.txt", "tool_version.txt"):
            if (work / basename).exists():
                shutil.copy2(work / basename, evidence / basename)
        write_json(evidence / "result.json", entry)
        write_json(root / "summary.json", summary)
        print(name, "completed", flush=True)

    try:
        run("clock100", "clock", "clock.tcl", ["100"],
            "CLOCK_COMPLETE mhz=100", "clock_result.txt")
        run("clock125_regenerated", "clock", "clock.tcl", ["125", "regenerate"],
            "CLOCK_COMPLETE mhz=125", "clock_result.txt")
        regenerated = xci_semantics(root / "clock")
        run("clock125_clean", "clock_clean", "clock.tcl", ["125"],
            "CLOCK_COMPLETE mhz=125", "clock_result.txt")
        summary["clean_rebuild_semantics_equal"] = regenerated == xci_semantics(root / "clock_clean")
        if not summary["clean_rebuild_semantics_equal"]:
            raise RuntimeError("Clean rebuild changed XCI parameter semantics")
        run("fifo_positive", "fifo", "fifo.tcl", ["0"], "FIFO_COMPLETE", "fifo_result.txt")
        run("fifo_negative", "fifo_negative", "fifo.tcl", ["1"],
            "NEGATIVE_CONTROL_DETECTED", "fifo_result.txt")
        summary["status"] = "pass"
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        summary["status"] = "fail"
        summary["error"] = str(exc)
        print(str(exc), file=sys.stderr)
    finally:
        summary["sources_unchanged"] = initial == source_hashes(package) == source_hashes(root)
        if not summary["sources_unchanged"]:
            summary["status"] = "fail"
        write_json(root / "summary.json", summary)
    print("Summary:", root / "summary.json", flush=True)
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
