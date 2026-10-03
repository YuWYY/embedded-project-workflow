#!/usr/bin/env python3
"""Narrow, fail-closed CubeMX 6.18.1 / G474RE CMSIS-RTOS2 change adapter.

Copyright (c) 2026 YuWYY. SPDX-License-Identifier: MIT
Only generates and rebuilds an already isolated, integrated project. Never flashes.
The IOC remains authoritative; a plan is a disposable, source-bound edit receipt.
"""
from pathlib import Path
import argparse
import configparser
import ctypes
import hashlib
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile

IMPLEMENTATION_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
PROFILE = {
    "id": "windows-cubemx-6.18.1-g474re-cmsis2-armcc5-v1",
    "platform": "Windows", "cubemx": "6.18.1", "database": "DB.6.0.181",
    "firmware": "STM32Cube FW_G4 V1.6.3", "freertos": "10.3.1",
    "cmsis_wrapper": "ST CMSIS-RTOS2", "compiler": "5.06 update 7 (build 960)",
    "pack": "Keil.STM32G4xx_DFP.2.0.0", "device": "STM32G474RE",
    "stack_unit": "32-bit words", "queue_unit": "uint32_t elements",
    "bytes_per_word": 4,
}
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FREE_KEYS = {"FREERTOS.Tasks01", "FREERTOS.Queues01", "FREERTOS.FootprintOK",
             "FREERTOS.IPParameters", "FREERTOS.configTOTAL_HEAP_SIZE"}
FORBIDDEN_ENV = ("PROTOCOL_TEST_EXE", "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                 "PYTHONPATH", "PYTHONSTARTUP")


class AdapterError(Exception):
    """A failed precondition or evidence check (also effective under python -O)."""


def require(condition, message):
    if not condition:
        raise AdapterError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def inside(path, root):
    return Path(path).resolve().is_relative_to(Path(root).resolve())


def checked_path(path, roots, label, exists=True):
    reject_links(path)
    path = Path(path).resolve()
    require(any(inside(path, r) for r in roots), f"{label} escapes allowed roots: {path}")
    require(not exists or path.exists(), f"Missing {label}: {path}")
    return path


def reject_links(path):
    require(not any(character in str(path) for character in ('"', "\r", "\n", "\x00")),
            "Path contains unsupported script/control characters")
    original = Path(os.path.abspath(path))
    for component in (original, *original.parents):
        if component.exists() or component.is_symlink():
            attrs = getattr(component.lstat(), "st_file_attributes", 0)
            require(not component.is_symlink() and not (attrs & 0x400),
                    f"Reparse points/symlinks/junctions are unsupported: {component}")


def integer(text, label):
    require(bool(re.fullmatch(r"[1-9][0-9]*", str(text))), f"{label} must be a positive decimal integer")
    value = int(text)
    require(value <= 0x3FFFFFFF, f"{label} overflows 32-bit byte count")
    return value


def positive_timeout(value):
    try:
        seconds = float(value)
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError("timeout must be positive and finite") from exc
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be positive and finite")
    return seconds


def failure_type(exc, phase=None):
    if isinstance(exc, KeyboardInterrupt):
        return "interrupt"
    if isinstance(exc, subprocess.TimeoutExpired):
        return "timeout"
    if phase == "start_process":
        return "process_start"
    if isinstance(exc, AdapterError):
        return "validation"
    return "io" if isinstance(exc, OSError) else "unexpected"


def parse_ioc(data):
    """Parse only the two known table formats; keep the original byte lines."""
    require(isinstance(data, bytes), "IOC parser requires bytes")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AdapterError("IOC must be UTF-8") from exc
    require("\x00" not in text, "NUL in IOC")
    values = {}
    for line in text.splitlines():
        if not line or line.startswith("#"):
            continue
        require("=" in line, f"Malformed IOC line: {line[:80]}")
        key, value = line.split("=", 1)
        require(key and key.strip() == key and key not in values, f"Duplicate or malformed IOC key: {key}")
        values[key] = value
    required = {"File.Version": "6", "MxCube.Version": PROFILE["cubemx"], "MxDb.Version": PROFILE["database"],
                "ProjectManager.FirmwarePackage": PROFILE["firmware"],
                "VP_FREERTOS_VS_CMSIS_V2.Mode": "CMSIS_V2",
                "Mcu.UserName": "STM32G474RETx", "ProjectManager.KeepUserCode": "true",
                "ProjectManager.LibraryCopy": "0", "ProjectManager.UnderRoot": "false",
                "ProjectManager.TargetToolchain": "MDK-ARM V5.27"}
    for key, expected in required.items():
        require(values.get(key) == expected, f"Unsupported profile: {key} must be {expected}")
    require(values.get("ProjectManager.ProjectBuild", "false") == "false", "CubeMX automatic project build is unsupported")
    for key in ("ProjectManager.UAScriptBeforePath", "ProjectManager.UAScriptAfterPath"):
        require(not values.get(key), f"CubeMX user hook is forbidden: {key}")
    unknown = sorted(k for k in values if k.startswith("FREERTOS.") and k not in FREE_KEYS)
    require(not unknown, f"Unsupported FREERTOS keys: {unknown}")
    params = values.get("FREERTOS.IPParameters", "").split(",")
    require(len(params) == len(set(params)) and all("FREERTOS." + p in FREE_KEYS for p in params),
            "Unsupported or duplicate FREERTOS.IPParameters")
    objects = {"tasks": [], "queues": []}
    names, symbols = set(), set()
    for key, kind, count in (("FREERTOS.Tasks01", "tasks", 9), ("FREERTOS.Queues01", "queues", 7)):
        require(values.get(key), f"Missing/empty {key}")
        for row in values[key].split(";"):
            fields = row.split(",")
            require(len(fields) == count, f"Unsupported {key} shape: expected {count} fields")
            name = fields[0]
            require(IDENT.fullmatch(name) and name not in names, f"Duplicate or invalid object name: {name}")
            names.add(name)
            if kind == "tasks":
                name, priority, words, entry, external, argument, allocation, stack, tcb = fields
                require(priority.isdecimal() and (int(priority) in (0, 1, 56) or 8 <= int(priority) <= 55),
                        f"Unsupported priority for {name}")
                require(external == "As external" and argument == "NULL", f"Unsupported entry shape for {name}")
                require(IDENT.fullmatch(entry), f"Invalid entry: {entry}")
                require(allocation in ("Static", "Dynamic"), f"Unsupported allocation: {allocation}")
                require(allocation != "Dynamic" or (stack, tcb) == ("NULL", "NULL"), f"Dynamic buffers must be NULL: {name}")
                owned = [name + "Handle", name + "_attributes", entry] + ([stack, tcb] if allocation == "Static" else [])
                item = {"name": name, "priority": int(priority), "stack_words": integer(words, name),
                        "entry": entry, "allocation": allocation, "stack": stack, "tcb": tcb, "fields": fields}
            else:
                name, capacity, ctype, zero, allocation, storage, tcb = fields
                require((ctype, zero, allocation) == ("uint32_t", "0", "Static"), f"Unsupported queue shape: {name}")
                owned = [name + "Handle", name + "_attributes", storage, tcb]
                item = {"name": name, "capacity_elements": integer(capacity, name), "storage": storage,
                        "tcb": tcb, "allocation": allocation, "fields": fields}
            for symbol in owned:
                require(IDENT.fullmatch(symbol) and symbol != "NULL" and symbol not in symbols,
                        f"Duplicate or invalid RTOS symbol: {symbol}")
                symbols.add(symbol)
            objects[kind].append(item)
    return {"values": values, **objects}


def assignments(items, objects, unit):
    edits = {}
    existing = {item["name"]: item for item in objects}
    for assignment in items:
        require(assignment.count("=") == 1, f"Use NAME=VALUE for {unit}")
        name, value = assignment.split("=", 1)
        require(name in existing, f"Unknown object name: {name}")
        require(name not in edits, f"Duplicate requested change: {name}")
        value = integer(value, unit)
        require(value != existing[name][unit], f"No change requested for {name}")
        edits[name] = value
    return edits


def edit_ioc(data, task_changes, queue_changes):
    parsed = parse_ioc(data)
    replacements = {}
    for key, kind, changes, index in (("FREERTOS.Tasks01", "tasks", task_changes, 2),
                                       ("FREERTOS.Queues01", "queues", queue_changes, 1)):
        names = {obj["name"] for obj in parsed[kind]}
        require(set(changes) <= names, f"Unknown names in {key} edit")
        rows = []
        for obj in parsed[kind]:
            fields = list(obj["fields"])
            if obj["name"] in changes:
                fields[index] = str(integer(changes[obj["name"]], obj["name"]))
            rows.append(",".join(fields))
        replacements[key.encode()] = ";".join(rows).encode()
    output = []
    for line in data.splitlines(keepends=True):
        bare = line.rstrip(b"\r\n")
        ending = line[len(bare):]
        prefix = b"\xef\xbb\xbf" if bare.startswith(b"\xef\xbb\xbf") else b""
        key = bare[len(prefix):].split(b"=", 1)[0]
        if key in replacements:
            line = prefix + key + b"=" + replacements[key] + ending
        output.append(line)
    result = b"".join(output)
    parse_ioc(result)
    return result


def snapshot(project):
    result = {}
    for path in sorted(Path(project).rglob("*")):
        require(not path.is_symlink() and not (hasattr(path, "is_junction") and path.is_junction()),
                f"Links/junctions are unsupported inside the project: {path}")
        if path.is_file():
            checked_path(path, [project], "snapshot input")
            result[path.relative_to(project).as_posix()] = sha(path)
    return result


def check_snapshot(project, expected):
    current = snapshot(project)
    changed = sorted(k for k in set(current) | set(expected) if current.get(k) != expected.get(k))
    require(not changed, f"Project changed after plan (create a new plan): {changed[:20]}")


def compilation_inputs(project, explicit_paths=()):
    """Bind build inputs on both sides of the compiler, excluding build products."""
    extensions = {".c", ".h", ".s", ".inc", ".cpp", ".hpp", ".ioc", ".sct", ".uvprojx"}
    result = {name: digest for name, digest in snapshot(project).items()
              if Path(name).suffix.lower() in extensions or name == ".mxproject"}
    for path in explicit_paths:
        path = checked_path(path, [project], "explicit compilation input")
        result[path.relative_to(project).as_posix()] = sha(path)
    return result


def check_compilation_inputs(project, expected):
    current = compilation_inputs(project, [Path(project) / name for name in expected])
    changed = sorted(name for name in set(expected) | set(current) if expected.get(name) != current.get(name))
    require(not changed, f"Compilation inputs changed during rebuild: {changed[:20]}")
    return current


def read_xml(path):
    data = Path(path).read_bytes()
    require(b"<!DOCTYPE" not in data.upper() and b"<!ENTITY" not in data.upper(), "XML entities are unsupported")
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise AdapterError(f"Malformed project XML: {path}: {exc}") from exc


def resolve_uv(text, base, roots, label, exists=True):
    require(text and not re.search(r"[$%<>|\r\n]", text), f"Unsupported {label} expansion/path: {text!r}")
    return checked_path(base / text.replace("\\", "/"), roots, label, exists)


def inspect_project(project, ioc, uvprojx, target_name, user_sources, vendor_roots=()):
    reject_links(project)
    project = Path(project).resolve()
    require(project.is_dir(), f"Project must already exist: {project}")
    ioc = checked_path(ioc, [project], "IOC")
    uvprojx = checked_path(uvprojx, [project], "uvprojx")
    require((project / ".mxproject").is_file(), "An existing CubeMX .mxproject is required")
    model = parse_ioc(ioc.read_bytes())
    inspect_mxproject(project, uvprojx.parent)
    for key in ("ProjectManager.MainLocation",):
        checked_path(project / model["values"].get(key, "Core/Src"), [project], key, exists=False)
    require(model["values"].get("ProjectManager.ToolChainLocation", "") == "", "Custom CubeMX toolchain location is unsupported")
    require(model["values"].get("ProjectManager.ProjectName") == uvprojx.stem,
            "IOC project name must match selected uvprojx")
    require(model["values"].get("ProjectManager.ProjectFileName") == ioc.name,
            "IOC project filename must match the selected IOC")
    root = read_xml(uvprojx)
    targets = root.findall(".//Target")
    matches = [t for t in targets if t.findtext("TargetName") == target_name]
    require(len(matches) == 1, f"Target must match exactly once: {target_name}")
    target = matches[0]
    require(target.findtext("pCCUsed", "") == r"5060960::V5.06 update 7 (build 960)::.\ARMCC",
            "Expected ARMCC 5.06u7 build 960 and the installed .\\ARMCC selection")
    require(target.findtext("uAC6") == "0", "ARM Compiler 6 is unsupported")
    require(target.findtext(".//PackID") == PROFILE["pack"], "Unsupported project device pack")
    require(target.findtext(".//Device", "").startswith("STM32G474RE"), "Unsupported project device")
    empty_hooks = check_hooks(target)
    # This profile copies vendor sources into the isolated project. Explicit
    # linked-source/include layouts are refused because a project-only snapshot
    # could not bind their changing external inputs to this one-off plan.
    roots = [project]
    sources = []
    for group in target.findall(".//Groups/Group"):
        require(group.findtext("./GroupOption/CommonProperty/IncludeInBuild", "1") != "0", "Excluded build groups are unsupported")
        for node in group.findall("./Files/File"):
            path = resolve_uv(node.findtext("FilePath"), uvprojx.parent, roots, "project source")
            require(path.is_file(), f"Project source is not a file: {path}")
            require(node.findtext(".//IncludeInBuild", "1") != "0", f"Excluded source is unsupported: {path}")
            require(node.findtext("FileType") in ("1", "2", "5"), f"Unsupported custom file action: {path}")
            sources.append(path)
    require(sources, "No compiled sources in target")
    require(len(sources) == len(set(str(p).casefold() for p in sources)), "A source is compiled more than once")
    # An object basename collision makes the expected MAP owner ambiguous.
    compiled = [p for p in sources if p.suffix.lower() in (".c", ".cpp", ".s")]
    stems = [p.stem.casefold() for p in compiled]
    require(len(stems) == len(set(stems)), "Ambiguous duplicate compilation object basename")
    for node in target.findall(".//IncludePath"):
        for text in (node.text or "").split(";"):
            if text.strip():
                resolve_uv(text.strip(), uvprojx.parent, roots, "include directory")
    outputs = {}
    for tag in ("OutputDirectory", "ListingPath"):
        value = target.findtext(".//" + tag)
        outputs[tag] = str(resolve_uv(value, uvprojx.parent, [project], tag, exists=False))
    name = target.findtext(".//OutputName")
    require(name and IDENT.fullmatch(name), "Unsupported output name")
    extra_inputs = []
    for tag in ("ScatterFile",):
        value = target.findtext(".//" + tag)
        if value:
            extra_inputs.append(str(resolve_uv(value, uvprojx.parent, roots, tag)))
    # Extra flags could include response files, plugins, or unbounded output paths.
    for node in target.findall(".//MiscControls"):
        require(not (node.text or "").strip(), "Nonempty custom compiler/linker MiscControls are unsupported")
    for tag in ("BinPath", "LibPath", "CustomArgument", "IncludeLibraryModules", "IncludeLibs", "IncludeLibsPath",
                "LinkerInputFile", "Misc", "pFcarmOut", "pFcarmGrp", "pFcArmRoot"):
        for node in target.findall(".//" + tag):
            require(not (node.text or "").strip(), f"Nonempty custom {tag} is unsupported")
    users = [checked_path(p, [project], "user source") for p in user_sources]
    require(users and len(users) == len(set(users)), "Specify unique --user-source files")
    for path in users:
        require(path.suffix.lower() == ".c" and sources.count(path) == 1, f"User source must compile once: {path}")
        require(path.relative_to(project).parts[0] not in ("Core", "Drivers", "Middlewares", "MDK-ARM"),
                f"User sources must use a dedicated application directory: {path}")
    for path in compiled:
        if path.relative_to(project).parts[0] not in ("Core", "Drivers", "Middlewares", "MDK-ARM"):
            require(path in users, f"List every application source with --user-source: {path}")
    permitted_creators = {(project / "Core/Src/app_freertos.c").resolve(),
                          (project / "Middlewares/Third_Party/FreeRTOS/Source/CMSIS_RTOS_V2/cmsis_os2.c").resolve()}
    for source in sources:
        if source.suffix.lower() == ".c" and source not in permitted_creators:
            body = strip_c_comments(source.read_text(encoding="utf-8-sig", errors="replace"))
            require(not re.search(r"\b(?:osThreadNew|osMessageQueueNew)\s*\(", body),
                    f"Additional direct RTOS object creation outside generated owner: {source}")
    owners = {}
    for task in model["tasks"]:
        expression = re.compile(r"\bvoid\s+" + re.escape(task["entry"]) + r"\s*\([^;{}]*\)\s*\{")
        candidates = [p for p in users if expression.search(strip_c_comments(p.read_text(encoding="utf-8-sig")))]
        require(len(candidates) == 1, f"Expected one user definition of {task['entry']}")
        owners[task["entry"]] = candidates[0].stem.lower() + ".o"
    return {"model": model, "sources": [str(p) for p in sources], "owners": owners,
            "extra_inputs": extra_inputs,
            "user_sources": [str(p) for p in users], "outputs": outputs,
            "output_name": name, "empty_enabled_hooks": empty_hooks}


def inspect_mxproject(project, mdk):
    """These native bookkeeping paths can be used for deletion during regeneration."""
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    try:
        parser.read_string((project / ".mxproject").read_text(encoding="utf-8-sig"))
    except configparser.Error as exc:
        raise AdapterError(f"Unsupported .mxproject: {exc}") from exc
    require(set(parser.sections()) <= {"PreviousLibFiles", "PreviousUsedKeilFiles", "PreviousGenFiles"},
            "Unsupported .mxproject section")
    for section in parser.sections():
        for key, value in parser[section].items():
            if section == "PreviousLibFiles":
                require(key == "LibFiles", f"Unsupported .mxproject key: {section}/{key}")
                base, ispath = project, True
            elif section == "PreviousUsedKeilFiles":
                require(key in ("SourceFiles", "HeaderPath", "CDefines"), f"Unsupported .mxproject key: {section}/{key}")
                base, ispath = mdk, key != "CDefines"
            else:
                ispath = bool(re.fullmatch(r"(?:HeaderFiles|SourceFiles|HeaderPath|SourcePath)(?:#\d+)?", key))
                require(ispath or key in ("AdvancedFolderStructure", "HeaderFileListSize", "HeaderFolderListSize", "SourceFileListSize", "SourceFolderListSize"),
                        f"Unsupported .mxproject key: {section}/{key}")
                base = mdk
            if ispath:
                for item in value.split(";"):
                    if item:
                        resolve_uv(item, base, [project], ".mxproject generated/deletion path", exists=False)


def check_hooks(target):
    empty = []
    for block in ("BeforeCompile", "BeforeMake", "AfterMake"):
        for action in target.findall(".//" + block):
            for index in (1, 2):
                flag = action.findtext(f"RunUserProg{index}", "0")
                require(flag in ("0", "1"), f"Invalid {block} hook flag")
                if flag == "1":
                    command = action.findtext(f"UserProg{index}Name", "").strip()
                    require(not command, f"Enabled nonempty project hook is forbidden: {block}/{index}")
                    require(block == "AfterMake",
                            f"Only known empty AfterMake action slots are supported: {block}/{index}")
                    empty.append(f"{block}/{index}")
    return empty


def strip_c_comments(text):
    return re.sub(r"/\*.*?\*/|//[^\r\n]*", "", text, flags=re.S)


def user_regions(project):
    regions = {}
    pattern = re.compile(rb"/\* USER CODE BEGIN ([^\r\n]*?) \*/(.*?)/\* USER CODE END \1 \*/", re.S)
    for path in sorted(Path(project).rglob("*")):
        if path.is_file() and path.suffix.lower() in (".c", ".h"):
            for number, match in enumerate(pattern.finditer(path.read_bytes())):
                key = path.relative_to(project).as_posix() + ":" + str(number) + ":" + match[1].decode("utf-8")
                # Native generation can normalize EOLs; preserve all actual region text.
                regions[key] = hashlib.sha256(match[2].replace(b"\r\n", b"\n")).hexdigest()
    require(regions, "No existing USER CODE regions found")
    return regions


def user_hashes(project, user_sources):
    paths = set()
    for source in user_sources:
        # Headers and other application files beside the explicitly owned C source are retained.
        folder = Path(source).parent
        require(folder != Path(project), "Keep user sources in a dedicated application directory")
        for path in folder.rglob("*"):
            if path.is_file():
                checked_path(path, [project], "user-owned file")
                paths.add(path)
    return {p.relative_to(project).as_posix(): sha(p) for p in sorted(paths)}


def pe_version(path):
    require(os.name == "nt", "This installation profile is Windows-only")
    library = ctypes.windll.version
    size = library.GetFileVersionInfoSizeW(str(path), None)
    require(size > 0, f"Missing actual Windows version resource: {path}")
    data = ctypes.create_string_buffer(size)
    require(library.GetFileVersionInfoW(str(path), 0, size, data), f"Cannot read version: {path}")
    pointer, length = ctypes.c_void_p(), ctypes.c_uint()
    # The Launch4j launcher fixed fields are 4.1.0.0; CubeMX's actual product
    # version is in localized StringFileInfo. Prefer that installed resource.
    translations = ctypes.c_void_p()
    translations_size = ctypes.c_uint()
    if library.VerQueryValueW(data, "\\VarFileInfo\\Translation", ctypes.byref(translations), ctypes.byref(translations_size)):
        codes = ctypes.cast(translations, ctypes.POINTER(ctypes.c_ushort))
        for offset in range(0, translations_size.value // 2, 2):
            key = f"\\StringFileInfo\\{codes[offset]:04x}{codes[offset + 1]:04x}\\FileVersion"
            if library.VerQueryValueW(data, key, ctypes.byref(pointer), ctypes.byref(length)):
                return ctypes.wstring_at(pointer).strip()
    require(library.VerQueryValueW(data, "\\", ctypes.byref(pointer), ctypes.byref(length)), "Invalid version resource")
    words = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32))
    return ".".join(str(x) for x in (words[2] >> 16, words[2] & 65535, words[3] >> 16, words[3] & 65535))


def doctor(paths):
    """Read installed artifacts, never treat a registry label as version proof."""
    paths = {k: str(Path(v).resolve()) for k, v in paths.items()}
    for key, value in paths.items():
        require(Path(value).exists(), f"Missing installed {key}: {value}")
    cube, fw, uv4, armcc, pack = (Path(paths[k]) for k in ("cubemx", "firmware", "uv4", "armcc", "pack"))
    require(cube.is_file() and uv4.is_file() and armcc.is_file(), "Vendor executables must be files")
    require(fw.is_dir() and pack.is_dir(), "Firmware and device pack must be directories")
    artifacts = {}
    require(zipfile.is_zipfile(cube), "CubeMX executable must be its supplied executable JAR")
    with zipfile.ZipFile(cube) as archive:
        manifest = archive.read("META-INF/MANIFEST.MF").decode("utf-8", errors="replace")
    require("com.st.microxplorer.maingui.STM32CubeMX" in manifest, "Unexpected CubeMX JAR entrypoint")
    cube_version = pe_version(cube)
    require(cube_version in ("6.18.1", "6.18.1.0", "6.18.1-RC2"), f"Actual CubeMX PE version is not 6.18.1: {cube_version}")
    artifacts["cubemx_manifest"] = manifest.strip()
    db_files = [cube.parent / "db/package.xml"]
    db_files += [p for p in (cube.parent / "db").glob("*Version*") if p.is_file() and p not in db_files]
    db_files += [p for p in (cube.parent / "db" / "properties").glob("*") if p.is_file()] if (cube.parent / "db" / "properties").is_dir() else []
    matched = [p for p in db_files if p.is_file() and p.suffix.lower() == ".xml"
               and any(n.get("Release") == "DB.6.0.181" for n in read_xml(p).findall(".//PackDescription"))]
    require(matched, "Actual CubeMX database metadata does not identify DB.6.0.181")
    artifacts["database"] = {str(p): sha(p) for p in matched}
    package = fw / "package.xml"
    require(package.is_file(), "Missing firmware package.xml")
    require(any(n.get("Patch") == "FW.G4.1.6.3" for n in read_xml(package).findall(".//PackDescription")),
            "Unsupported firmware package metadata")
    freertos = fw / "Middlewares/Third_Party/FreeRTOS/Source/include/task.h"
    require(freertos.is_file(), "Missing FreeRTOS task.h")
    version_text = freertos.read_text(encoding="utf-8", errors="replace")
    require(re.search(r'tskKERNEL_VERSION_NUMBER\s+"V10\.3\.1"', version_text), "FreeRTOS version is not 10.3.1")
    wrapper = fw / "Middlewares/Third_Party/FreeRTOS/Source/CMSIS_RTOS_V2/cmsis_os2.c"
    require(wrapper.is_file(), "ST CMSIS-RTOS2 wrapper is missing")
    wrapper_text = wrapper.read_text(encoding="utf-8", errors="replace")
    require("CMSIS RTOS2 wrapper for FreeRTOS" in wrapper_text and "osThreadNew" in wrapper_text and "osMessageQueueNew" in wrapper_text,
            "Unexpected CMSIS-RTOS2 wrapper")
    pdscs = list(pack.glob("*.pdsc"))
    require(len(pdscs) == 1, "Expected one installed device-pack descriptor")
    pdsc = read_xml(pdscs[0])
    require(pdsc.findtext("vendor") == "Keil" and pdsc.findtext("name") == "STM32G4xx_DFP",
            "Unsupported pack descriptor")
    releases = pdsc.findall(".//release")
    require(releases and releases[0].get("version") == "2.0.0", "Installed pack is not release 2.0.0")
    require(pack.name == "2.0.0", "Select the actual installed 2.0.0 pack directory")
    compiler_version = pe_version(armcc)
    require(armcc.resolve() == (uv4.parent.parent / "ARM/ARMCC/bin/armcc.exe").resolve(),
            "The supplied ARMCC must be the compiler selected by this Keil installation")
    # ARMCC's PE resource can identify its component build (189), while --vsn
    # identifies the installed suite release (960). Record both actual sources.
    version_env = os.environ.copy()
    for key in FORBIDDEN_ENV:
        version_env.pop(key, None)
    version_process = subprocess.run([str(armcc), "--vsn"], capture_output=True, timeout=30,
                                     env=version_env, creationflags=subprocess.CREATE_NO_WINDOW)
    compiler_banner = (version_process.stdout + version_process.stderr).decode("utf-8", errors="replace").strip()
    require(version_process.returncode == 0 and "ARM Compiler 5.06 update 7 (build 960)" in compiler_banner,
            f"Unsupported actual ARMCC suite banner: {compiler_banner}")
    java = cube.parent / "jre/bin/java.exe"
    require(java.is_file(), "CubeMX bundled Java is missing")
    for label, path in (("firmware", package), ("freertos", freertos), ("cmsis_wrapper", wrapper),
                        ("pack", pdscs[0]), ("armcc", armcc), ("uv4", uv4), ("cubemx", cube), ("java", java)):
        artifacts[label] = {"path": str(path), "sha256": sha(path)}
    return {"profile": PROFILE, "paths": paths, "artifacts": artifacts,
            "actual_armcc_version": compiler_version, "actual_armcc_banner": compiler_banner,
            "actual_cubemx_version": cube_version, "actual_uv4_version": pe_version(uv4),
            "runtime": "NOT_RUN"}


def vendor_roots(paths):
    return [Path(paths["firmware"]), Path(paths["pack"]), Path(paths["armcc"]).parent.parent]


def make_plan(project, ioc, uvprojx, target, users, task_items, queue_items, tools):
    for path in (project, ioc, uvprojx):
        reject_links(path)
    project, ioc, uvprojx = (Path(p).resolve() for p in (project, ioc, uvprojx))
    installation = doctor(tools)
    state = inspect_project(project, ioc, uvprojx, target, users, vendor_roots(installation["paths"]))
    tasks = assignments(task_items, state["model"]["tasks"], "stack_words")
    queues = assignments(queue_items, state["model"]["queues"], "capacity_elements")
    require(tasks or queues, "At least one actual object change is required")
    after = edit_ioc(ioc.read_bytes(), tasks, queues)
    manifest = snapshot(project)
    plan = {"schema": 1, "profile": PROFILE, "adapter_sha256": IMPLEMENTATION_SHA256,
            "project": str(project), "ioc": str(ioc),
            "uvprojx": str(uvprojx), "target": target, "installation": installation,
            "task_changes": tasks, "queue_changes": queues,
            "before": state["model"], "after": parse_ioc(after),
            "requested_ioc_sha256": hashlib.sha256(after).hexdigest(),
            "snapshot": manifest, "user_sources": state["user_sources"],
            "user_hashes": user_hashes(project, state["user_sources"]),
            "user_regions": user_regions(project), "owners": state["owners"],
            "outputs": state["outputs"], "output_name": state["output_name"],
            "runtime": "NOT_RUN"}
    plan["changes"] = []
    for kind, unit, changes in (("tasks", "stack_words", tasks), ("queues", "capacity_elements", queues)):
        for obj in state["model"][kind]:
            if obj["name"] in changes:
                after_value = changes[obj["name"]]
                plan["changes"].append({"name": obj["name"], "kind": kind, "unit": unit,
                                        "before": obj[unit], "after": after_value,
                                        "before_bytes": obj[unit] * 4, "after_bytes": after_value * 4})
    plan["plan_id"] = hashlib.sha256(canonical(plan)).hexdigest()
    return plan


def load_plan(path):
    plan = json.loads(Path(path).read_text(encoding="utf-8"))
    identity = plan.pop("plan_id", None)
    require(identity == hashlib.sha256(canonical(plan)).hexdigest(), "Plan identity mismatch")
    plan["plan_id"] = identity
    require(plan.get("schema") == 1 and plan.get("profile") == PROFILE, "Unsupported plan profile/schema")
    require(plan.get("adapter_sha256") == IMPLEMENTATION_SHA256, "Adapter changed since plan; create a new plan")
    return plan


def hidden_options():
    kwargs = {}
    if os.name == "nt":
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        kwargs["startupinfo"] = startup
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return kwargs


def stop_owned_process(process):
    cleanup = {"pid": process.pid, "status": "NOT_NEEDED", "tree_kill_returncode": None}
    if process.poll() is not None:
        return cleanup
    cleanup["status"] = "INCOMPLETE"
    if os.name == "nt":
        try:
            taskkill = Path(os.environ["SystemRoot"]) / "System32/taskkill.exe"
            result = subprocess.run([str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, **hidden_options())
            cleanup["tree_kill_returncode"] = result.returncode
        except (KeyError, OSError, subprocess.TimeoutExpired) as exc:
            cleanup["tree_kill_error"] = str(exc)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            cleanup["tree_kill_returncode"] = 0
        except OSError as exc:
            cleanup["tree_kill_error"] = str(exc)
    try:
        if cleanup["tree_kill_returncode"] != 0 and process.poll() is None:
            process.kill()
            cleanup["direct_kill"] = True
        process.wait(timeout=5)
        if cleanup["tree_kill_returncode"] == 0:
            cleanup["status"] = "COMPLETE"
    except (OSError, subprocess.TimeoutExpired) as exc:
        cleanup["wait_error"] = str(exc)
    return cleanup


def run(command, cwd, log, env, timeout=360, record=None):
    timeout = positive_timeout(timeout)
    log = Path(log)
    kwargs = hidden_options()
    if os.name != "nt":
        kwargs["start_new_session"] = True
    # The caller retains this very record even if launch, waiting, or saving fails.
    # Do not recover it from a possibly stale or unwritable result file.
    if record is None:
        record = {}
    record.update(command=[str(x) for x in command], status="STARTED", exit_code=None,
                  timeout_seconds=timeout, terminal_state="RUNNING")
    write_json(log.with_suffix(".json"), record)
    start = time.monotonic()
    proc = None
    phase = "open_log"
    try:
        with log.open("wb") as output:
            phase = "start_process"
            proc = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                    stdout=output, stderr=subprocess.STDOUT, **kwargs)
            record["pid"] = proc.pid
            phase = "save_launched_record"
            write_json(log.with_suffix(".json"), record)
            phase = "wait"
            try:
                record["exit_code"] = proc.wait(timeout=timeout)
            except (subprocess.TimeoutExpired, KeyboardInterrupt):
                record["cleanup"] = stop_owned_process(proc)
                record["exit_code"] = proc.poll()
                raise
        record.update(status="EXITED", terminal_state="EXITED")
    except BaseException as exc:
        if proc is not None and proc.poll() is None and "cleanup" not in record:
            record["cleanup"] = stop_owned_process(proc)
            record["exit_code"] = proc.poll()
        if proc is not None:
            record["exit_code"] = proc.poll()
        status = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "TIMEOUT" if isinstance(exc, subprocess.TimeoutExpired) else "FAILED"
        record.update(status=status, terminal_state=status, error=str(exc) or type(exc).__name__,
                      error_type=type(exc).__name__, failure_type=failure_type(exc, phase), failure_phase=phase)
        raise
    finally:
        record["seconds"] = round(time.monotonic() - start, 3)
        write_json(log.with_suffix(".json"), record)
    return record


def check_generation(record, log, products, started_ns, before_generated_hash):
    require(record.get("exit_code") == 0, "CubeMX process failed")
    body = Path(log).read_text(encoding="utf-8", errors="replace")
    require(not re.search(r"Exception|Code generation failed|FileNotFound|generation.*(?:failed|error)", body, re.I),
            "CubeMX log reports generation failure")
    for path in products:
        require(path.is_file() and path.stat().st_size > 0, f"Missing generated product: {path}")
    # CubeMX intentionally leaves unchanged files (for example main.c) untouched.
    # The RTOS output must be freshly rewritten and differ for a nonempty edit.
    require(products[0].stat().st_mtime_ns >= started_ns - 2_000_000_000, f"Stale generated product: {products[0]}")
    require(sha(products[0]) != before_generated_hash, "RTOS source did not change after requested IOC edit")


def check_build(record, log, map_path, image_path, started_ns):
    require(Path(log).is_file(), "Keil build log is missing")
    body = Path(log).read_text(encoding="utf-8", errors="replace")
    match = re.search(r"(\d+) Error\(s\), (\d+) Warning\(s\)", body)
    require(match and int(match[1]) == 0 and record.get("exit_code") in (0, 1), "Keil rebuild failed or has no complete summary")
    for path in (map_path, image_path):
        require(path.is_file() and path.stat().st_size > 0, f"Missing build product: {path}")
        require(path.stat().st_mtime_ns >= started_ns - 2_000_000_000, f"Stale build product: {path}")
    return {"errors": 0, "warnings": int(match[2])}


def check_user_compilation(log, user_sources):
    body = Path(log).read_text(encoding="utf-8", errors="replace")
    for path in user_sources:
        matches = re.findall(r"^compiling\s+" + re.escape(Path(path).name) + r"\.\.\.\s*$", body, re.M | re.I)
        require(len(matches) == 1, f"Rebuild log must show exactly one compilation of user source: {path}")
    require("V5.06 update 7 (build 960)" in body, "Rebuild log does not identify the expected compiler suite")


def c_initializer(body, ctype, symbol):
    found = re.findall(r"\b" + re.escape(ctype) + r"\s+" + re.escape(symbol) + r"\s*=\s*\{(.*?)\}\s*;", body, re.S)
    require(len(found) == 1, f"Expected one attribute initializer: {symbol}")
    fields = re.findall(r"\.([A-Za-z_]\w*)\s*=\s*([^,]+)", found[0])
    require(len(fields) == len(dict(fields)), f"Duplicate attribute field: {symbol}")
    return {key: re.sub(r"\s+", "", value) for key, value in fields}


def map_size(text, symbol, expected):
    values = re.findall(r"^\s*" + re.escape(symbol) + r"\s+0x[0-9a-fA-F]+\s+Data\s+(\d+)\s", text, re.M)
    require(values == [str(expected)], f"MAP byte size mismatch for {symbol}: expected {expected}, got {values}")


def verify_outputs(plan, map_path):
    project = Path(plan["project"])
    model = parse_ioc(Path(plan["ioc"]).read_bytes())
    require(model["tasks"] == plan["after"]["tasks"] and model["queues"] == plan["after"]["queues"],
            "Generated IOC does not retain requested object configuration")
    state = inspect_project(project, plan["ioc"], plan["uvprojx"], plan["target"], plan["user_sources"],
                            vendor_roots(plan["installation"]["paths"]))
    require(state["owners"] == plan["owners"], "Expected user entry owners changed")
    require(user_hashes(project, plan["user_sources"]) == plan["user_hashes"], "User-owned application files changed")
    require(user_regions(project) == plan["user_regions"], "USER CODE region retention failed")
    source = project / "Core/Src/app_freertos.c"
    body = strip_c_comments(source.read_text(encoding="utf-8-sig"))
    map_path = checked_path(map_path, [project], "MAP")
    text = map_path.read_text(encoding="utf-8", errors="replace")
    threads = re.findall(r"\b(\w+)\s*=\s*osThreadNew\s*\(\s*(\w+)\s*,\s*([^,]+),\s*&\s*(\w+)\s*\)", body)
    queues = re.findall(r"\b(\w+)\s*=\s*osMessageQueueNew\s*\(\s*(\d+)\s*,\s*sizeof\s*\(\s*uint32_t\s*\)\s*,\s*&\s*(\w+)\s*\)", body)
    # Count every call too: unparsed creations and duplicate creations cannot disappear.
    require(len(threads) == len(model["tasks"]) == len(re.findall(r"\bosThreadNew\s*\(", body)), "Nonunique/unsupported task creation")
    require(len(queues) == len(model["queues"]) == len(re.findall(r"\bosMessageQueueNew\s*\(", body)), "Nonunique/unsupported queue creation")
    for task in model["tasks"]:
        name, entry, words = task["name"], task["entry"], task["stack_words"]
        require(threads.count((name + "Handle", entry, "NULL", name + "_attributes")) == 1,
                f"Task creation/attributes binding mismatch: {name}")
        attributes = c_initializer(body, "osThreadAttr_t", name + "_attributes")
        require(attributes.get("name") == '"' + name + '"', f"Task attribute name mismatch: {name}")
        priority = task["priority"]
        if priority in (0, 1, 56):
            priority_name = {0: "osPriorityNone", 1: "osPriorityIdle", 56: "osPriorityISR"}[priority]
        else:
            priority_name = {8: "osPriorityLow", 16: "osPriorityBelowNormal", 24: "osPriorityNormal",
                             32: "osPriorityAboveNormal", 40: "osPriorityHigh", 48: "osPriorityRealtime"}[priority // 8 * 8]
            if priority % 8:
                priority_name += str(priority % 8)
        require(attributes.get("priority") == "(osPriority_t)" + priority_name, f"Task priority changed: {name}")
        owner = plan["owners"][entry]
        # Only the actual global symbol table definition counts, not a cross-reference line.
        symbol_lines = re.findall(r"^\s*" + re.escape(entry) + r"\s+0x[0-9a-fA-F]+\s+Thumb Code\s+\d+\s+([^\r\n]+)", text, re.M)
        require(len(symbol_lines) == 1 and re.match(re.escape(owner) + r"(?:\(|\s|$)", symbol_lines[0], re.I),
                f"Entry does not resolve to expected user object ({owner}): {entry}")
        if task["allocation"] == "Static":
            stack = task["stack"]
            require(len(re.findall(r"\buint32_t\s+" + re.escape(stack) + r"\s*\[\s*" + str(words) + r"\s*\]", body)) == 1,
                    f"Static stack declaration mismatch: {name}")
            require(attributes.get("stack_mem") == "&" + stack + "[0]" and attributes.get("stack_size") == "sizeof(" + stack + ")",
                    f"Static stack attributes mismatch: {name}")
            require(attributes.get("cb_mem") == "&" + task["tcb"] and attributes.get("cb_size") == "sizeof(" + task["tcb"] + ")",
                    f"Static task control block binding mismatch: {name}")
            map_size(text, stack, words * 4)
        else:
            require(attributes.get("stack_size") == str(words) + "*4", f"Dynamic stack byte count mismatch: {name}")
            require(not any(key in attributes for key in ("stack_mem", "cb_mem", "cb_size")), f"Dynamic task has static memory attributes: {name}")
            require(not re.search(r"\buint32_t\s+" + re.escape(name) + r"Stack\s*\[", body), f"Dynamic task has a static stack: {name}")
    for queue in model["queues"]:
        name, count, storage = queue["name"], queue["capacity_elements"], queue["storage"]
        require(queues.count((name + "Handle", str(count), name + "_attributes")) == 1, f"Queue creation/binding mismatch: {name}")
        attributes = c_initializer(body, "osMessageQueueAttr_t", name + "_attributes")
        require(attributes.get("name") == '"' + name + '"', f"Queue name mismatch: {name}")
        require(attributes.get("mq_mem") in ("&" + storage, "&" + storage + "[0]") and attributes.get("mq_size") == "sizeof(" + storage + ")",
                f"Queue storage attributes mismatch: {name}")
        require(attributes.get("cb_mem") == "&" + queue["tcb"] and attributes.get("cb_size") == "sizeof(" + queue["tcb"] + ")",
                f"Queue control block attributes mismatch: {name}")
        require(len(re.findall(r"\buint8_t\s+" + re.escape(storage) + r"\s*\[\s*" + str(count) + r"\s*\*\s*sizeof\s*\(\s*uint32_t\s*\)\s*\]", body)) == 1,
                f"Queue static storage declaration mismatch: {name}")
        map_size(text, storage, count * 4)
    config = strip_c_comments((project / "Core/Inc/FreeRTOSConfig.h").read_text(encoding="utf-8-sig"))
    for macro in ("configSUPPORT_STATIC_ALLOCATION", "configSUPPORT_DYNAMIC_ALLOCATION"):
        values = re.findall(r"^\s*#\s*define\s+" + macro + r"\s+([^\r\n]+)", config, re.M)
        require([value.strip() for value in values] == ["1"] and not re.search(r"^\s*#\s*undef\s+" + macro + r"\b", config, re.M),
                f"Required wrapper macro must be defined exactly once as 1: {macro}")
    return {"status": "PASS", "profile": PROFILE["id"], "plan_id": plan["plan_id"],
            "unique_creations_and_attributes": True, "user_sources_compiled_once": True,
            "entry_owners": plan["owners"], "user_source_retention": True, "user_code_retention": True,
            "static_storage_map_bytes": {**{t["stack"]: t["stack_words"] * 4 for t in model["tasks"] if t["allocation"] == "Static"},
                                         **{q["storage"]: q["capacity_elements"] * 4 for q in model["queues"]}},
            "map_sha256": sha(map_path), "runtime": "NOT_RUN", "board": "NOT_RUN"}


def disable_known_empty_hook(uvprojx, target_name):
    tree = ET.parse(uvprojx)
    targets = [t for t in tree.getroot().findall(".//Target") if t.findtext("TargetName") == target_name]
    require(len(targets) == 1, "Target disappeared after generation")
    empty = check_hooks(targets[0])
    if empty:
        for action in empty:
            block, index = action.split("/")
            targets[0].find(f".//{block}/RunUserProg{index}").text = "0"
        tree.write(uvprojx, encoding="utf-8", xml_declaration=True)
    return empty


def apply_plan(plan, work_root, reports, timeout=360):
    timeout = positive_timeout(timeout)
    for path in (plan["project"], work_root, reports):
        reject_links(path)
    project, reports, work_root = (Path(p).resolve() for p in (plan["project"], reports, work_root))
    require(work_root.is_dir() and project != work_root and inside(project, work_root),
            "Explicit existing isolated --work-root must contain the project as a child")
    require(not inside(reports, project) and not inside(project, reports), "Reports must be separate from the project")
    require(not reports.exists(), "Use a new reports directory; previous failure evidence is retained")
    # All checks happen before modifying the IOC or running a vendor executable.
    check_snapshot(project, plan["snapshot"])
    current_tools = doctor(plan["installation"]["paths"])
    require(current_tools == plan["installation"], "Installed tool metadata changed since plan")
    state = inspect_project(project, plan["ioc"], plan["uvprojx"], plan["target"], plan["user_sources"],
                            vendor_roots(current_tools["paths"]))
    ioc = Path(plan["ioc"])
    after = edit_ioc(ioc.read_bytes(), plan["task_changes"], plan["queue_changes"])
    require(hashlib.sha256(after).hexdigest() == plan["requested_ioc_sha256"], "Requested IOC hash mismatch")
    reports.mkdir(parents=True)
    outcome = {"status": "STARTED", "terminal_state": "RUNNING", "timeout_seconds": timeout,
               "plan_id": plan["plan_id"], "runtime": "NOT_RUN", "board": "NOT_RUN",
               "phase": "backup", "generation": {"status": "NOT_RUN", "exit_code": None},
               "build": {"status": "NOT_RUN", "exit_code": None}, "verification": {"status": "NOT_RUN"},
               "recovery": "IOC backup retained; native generation/build may partially modify multiple files; no atomic project rollback is promised."}
    write_json(reports / "result.json", outcome)
    temp = ioc.with_name(ioc.name + ".adapter-" + uuid.uuid4().hex + ".tmp")
    active_stage = None
    try:
        write_json(reports / "plan.json", plan)
        shutil.copy2(ioc, reports / "source-before.ioc")
        shutil.copy2(plan["uvprojx"], reports / "project-before.uvprojx")
        shutil.copy2(project / ".mxproject", reports / "source-before.mxproject")
        outcome["phase"] = "replace_ioc"
        write_json(reports / "result.json", outcome)
        with temp.open("xb") as stream:
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, ioc)
        (reports / "source-requested.ioc").write_bytes(after)
        env = os.environ.copy()
        for key in FORBIDDEN_ENV:
            env.pop(key, None)
        temporary = reports / "tmp"
        temporary.mkdir()
        env.update(TEMP=str(temporary), TMP=str(temporary), PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        paths = current_tools["paths"]
        script = reports / "generate.mxscript"
        script.write_text('\n'.join([f'config load "{ioc.as_posix()}"',
            'project toolchain "MDK-ARM V5.27"', f'project setCustomFWPath "{Path(paths["firmware"]).as_posix()}"',
            'project generate', 'exit', '']), encoding="utf-8")
        generated = project / "Core/Src/app_freertos.c"
        old_hash = sha(generated)
        outcome["phase"] = "generate"
        active_stage = "generation"
        outcome["generation"] = {"status": "RUNNING", "exit_code": None,
                                 "record": str(reports / "cubemx.json"), "timeout_seconds": timeout}
        write_json(reports / "result.json", outcome)
        start = time.time_ns()
        result = run([str(Path(paths["cubemx"]).parent / "jre/bin/java.exe"),
                      "--add-opens", "java.desktop/java.awt=ALL-UNNAMED", "--add-exports", "java.desktop/sun.awt=ALL-UNNAMED",
                      "-Dfile.encoding=UTF-8", "-jar", paths["cubemx"], "-q", str(script)],
                     project, reports / "cubemx.log", env, timeout=timeout, record=outcome["generation"])
        outcome["generation"] = result
        result["process_status"] = result.get("status", "EXITED")
        check_generation(result, reports / "cubemx.log", [generated, project / "Core/Src/main.c", Path(plan["uvprojx"])], start, old_hash)
        shutil.copy2(ioc, reports / "source-generated.ioc")
        outcome["phase"] = "validate_generated_project"
        write_json(reports / "result.json", outcome)
        outcome["disabled_known_empty_hooks"] = disable_known_empty_hook(plan["uvprojx"], plan["target"])
        state = inspect_project(project, ioc, plan["uvprojx"], plan["target"], plan["user_sources"], vendor_roots(paths))
        require(state["outputs"] == plan["outputs"] and state["output_name"] == plan["output_name"], "Output paths changed on regeneration")
        outcome["generation"]["terminal_state"] = "PASS"
        active_stage = None
        map_path = Path(state["outputs"]["ListingPath"]) / (state["output_name"] + ".map")
        image_path = Path(state["outputs"]["OutputDirectory"]) / (state["output_name"] + ".axf")
        # Move old products aside: a zero-exit no-op build cannot reuse them.
        outcome["phase"] = "archive_previous_build_products"
        write_json(reports / "result.json", outcome)
        for index, path in enumerate((map_path, image_path)):
            if path.exists():
                shutil.move(str(path), str(reports / ("previous-" + str(index) + path.suffix)))
        start = time.time_ns()
        build_log = reports / "keil.log"
        outcome["phase"] = "rebuild"
        active_stage = "build"
        outcome["build"] = {"status": "RUNNING", "exit_code": None,
                            "record": str(reports / "keil-process.json"), "timeout_seconds": timeout}
        outcome["compilation_inputs"] = compilation_inputs(project, state["sources"] + state["extra_inputs"])
        write_json(reports / "result.json", outcome)
        result = run([paths["uv4"], "-r", plan["uvprojx"], "-t", plan["target"], "-o", str(build_log)],
                     Path(plan["uvprojx"]).parent, reports / "keil-process.log", env,
                     timeout=timeout, record=outcome["build"])
        # Keep the actual process result before any generated/log/MAP checks.
        outcome["build"] = result
        result["process_status"] = result.get("status", "EXITED")
        check_compilation_inputs(project, outcome["compilation_inputs"])
        result.update(check_build(result, build_log, map_path, image_path, start))
        check_user_compilation(build_log, plan["user_sources"])
        outcome["build"]["terminal_state"] = "PASS"
        outcome["phase"] = "verify"
        active_stage = "verification"
        outcome["verification"] = {"status": "RUNNING"}
        write_json(reports / "result.json", outcome)
        outcome["verification"] = verify_outputs(plan, map_path)
        outcome["products"] = {"map": {"path": str(map_path), "sha256": sha(map_path)},
                               "axf": {"path": str(image_path), "sha256": sha(image_path)}}
        outcome["verified_snapshot"] = snapshot(project)
        outcome["status"] = "PASS"
        outcome["terminal_state"] = "PASS"
    except BaseException as exc:
        terminal = "INTERRUPTED" if isinstance(exc, KeyboardInterrupt) else "TIMEOUT" if isinstance(exc, subprocess.TimeoutExpired) else "FAILED"
        detail = outcome[active_stage] if active_stage else {}
        kind = detail.get("failure_type", failure_type(exc))
        if active_stage:
            if "command" in detail:
                detail.setdefault("process_status", detail.get("status"))
            detail.update(status=terminal, terminal_state=terminal, error=str(exc) or type(exc).__name__,
                          error_type=type(exc).__name__, failure_type=kind, failure_stage=outcome["phase"])
        outcome.update(status="FAILED", terminal_state=terminal, error=str(exc) or type(exc).__name__,
                       error_type=type(exc).__name__, failure_type=kind, failure_stage=outcome["phase"],
                       actual_exit_code=detail.get("exit_code"),
                       cleanup=detail.get("cleanup", {"status": "NOT_NEEDED"}))
        raise
    finally:
        if temp.exists():
            temp.unlink()
        write_json(reports / "result.json", outcome)
    return outcome


def add_tools(parser):
    for name in ("cubemx", "firmware", "uv4", "armcc", "pack"):
        parser.add_argument("--" + name, type=Path, required=True)


def tool_args(args):
    return {name: getattr(args, name) for name in ("cubemx", "firmware", "uv4", "armcc", "pack")}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    doc = commands.add_parser("doctor", help="Read actual installed metadata without changing installations")
    add_tools(doc)
    for command in ("inspect", "plan"):
        sub = commands.add_parser(command)
        for option in ("project", "ioc", "uvprojx"):
            sub.add_argument("--" + option, type=Path, required=True)
        sub.add_argument("--target", required=True)
        sub.add_argument("--user-source", action="append", type=Path, required=True)
        add_tools(sub)
        if command == "plan":
            sub.add_argument("--task-stack", action="append", default=[], metavar="NAME=WORDS")
            sub.add_argument("--queue-capacity", action="append", default=[], metavar="NAME=ELEMENTS")
            sub.add_argument("--output", type=Path, required=True)
    apply = commands.add_parser("apply")
    apply.add_argument("--plan", type=Path, required=True)
    apply.add_argument("--work-root", type=Path, required=True)
    apply.add_argument("--reports", type=Path, required=True)
    apply.add_argument("--timeout", type=positive_timeout, default=360,
                       help="Positive finite per-child timeout in seconds (default: 360)")
    verify = commands.add_parser("verify")
    verify.add_argument("--plan", type=Path, required=True)
    verify.add_argument("--reports", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor(tool_args(args))
        elif args.command == "inspect":
            installation = doctor(tool_args(args))
            result = inspect_project(args.project, args.ioc, args.uvprojx, args.target, args.user_source,
                                     vendor_roots(installation["paths"]))
            result["installation"] = installation
        elif args.command == "plan":
            require(not args.output.exists(), "Plan output already exists")
            require(not inside(args.output, args.project), "Plan output must be outside the snapshotted project")
            result = make_plan(args.project, args.ioc, args.uvprojx, args.target, args.user_source,
                               args.task_stack, args.queue_capacity, tool_args(args))
            require(args.output.parent.is_dir(), "Plan output parent must already exist")
            write_json(args.output, result)
        elif args.command == "apply":
            plan = load_plan(args.plan)
            result = apply_plan(plan, args.work_root, args.reports, args.timeout)
        else:
            plan = load_plan(args.plan)
            receipt = json.loads((args.reports / "result.json").read_text(encoding="utf-8"))
            require(receipt.get("status") == "PASS" and receipt.get("plan_id") == plan["plan_id"], "No successful apply receipt for this plan")
            check_snapshot(Path(plan["project"]), receipt["verified_snapshot"])
            for item in receipt["products"].values():
                require(sha(item["path"]) == item["sha256"], "Build product changed since apply")
            result = verify_outputs(plan, receipt["products"]["map"]["path"])
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "INTERRUPTED", "runtime": "NOT_RUN"}), file=sys.stderr)
        return 130
    except (AdapterError, OSError, ValueError, KeyError, ET.ParseError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc), "runtime": "NOT_RUN"}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
