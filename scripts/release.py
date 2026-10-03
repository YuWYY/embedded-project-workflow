#!/usr/bin/env python3
"""Validate and package only the explicitly reviewed public source files."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

VERSION = "0.7.0-beta.1"
SKILL = "skills/embedded-project-workflow"
MANIFEST = "release-manifest.json"
ALLOWLIST = "source-files.txt"
IGNORED_DIRS = {".git", "dist", ".cache", "__pycache__"}
PERSONAL_PATH = re.compile(r"\b[A-Za-z]:[\\/]|/(?:Users|home)/[^/\s]+/", re.I)
MARKDOWN_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\n]+)\)")


class InvalidRelease(Exception):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidRelease(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_path(root: Path, name: str) -> Path:
    posix = PurePosixPath(name)
    need(bool(name) and not posix.is_absolute(), f"Invalid source path: {name}")
    need("\\" not in name and ":" not in name and ".." not in posix.parts,
         f"Source path must be relative and normalized: {name}")
    need(posix.as_posix() == name, f"Noncanonical source path: {name}")
    path = root.joinpath(*posix.parts)
    need(not any(p.is_symlink() for p in (path, *path.parents)), f"Symlink disallowed: {name}")
    need(path.resolve().is_relative_to(root.resolve()), f"Source escapes repository: {name}")
    return path


def listed_sources(root: Path) -> list[str]:
    file = root / ALLOWLIST
    need(file.is_file(), f"Missing {ALLOWLIST}")
    names = [line.strip() for line in file.read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.startswith("#")]
    need(names == sorted(set(names)), "Source allowlist must be unique and sorted")
    need(ALLOWLIST in names and MANIFEST not in names, "Allowlist must include itself, not manifest")
    for name in names:
        need(source_path(root, name).is_file(), f"Missing source: {name}")
    return names


def actual_sources(root: Path) -> set[str]:
    found: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS for part in relative.parts):
            continue
        need(not path.is_symlink(), f"Unlisted symlink: {relative.as_posix()}")
        if path.is_file() and path.suffix != ".pyc":
            found.add(relative.as_posix())
    return found


def semantic_checks(root: Path, names: list[str]) -> None:
    required = {"README.md", "LICENSE", f"{SKILL}/SKILL.md", f"{SKILL}/agents/openai.yaml",
                "examples/vivado/README.md", "examples/vivado/scripts/rebuild.py"}
    need(required <= set(names), f"Missing required source entries: {sorted(required - set(names))}")
    entry = (root / SKILL / "SKILL.md").read_text(encoding="utf-8-sig")
    parts = entry.split("---", 2)
    need(len(parts) == 3 and not parts[0].strip(), "SKILL.md needs YAML frontmatter")
    fields = {}
    for line in parts[1].splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r"([a-z][a-z-]*):\s*(.+)", line)
        need(match is not None, "Frontmatter must use nonempty one-line scalar fields")
        key, value = match.groups()
        need(key not in fields, f"Duplicate frontmatter field: {key}")
        fields[key] = value.strip().strip('"').strip("'")
    need(fields.get("name") == "embedded-project-workflow", "Skill name mismatch")
    need(bool(fields.get("description")), "Missing skill description")
    need(set(fields) <= {"name", "description"}, "Review new frontmatter fields before release")
    ui = (root / SKILL / "agents/openai.yaml").read_text(encoding="utf-8-sig")
    need(re.search(r"(?m)^policy:\s*\n  allow_implicit_invocation: false\s*$", ui) is not None,
         "Explicit-only invocation policy missing")
    need("$embedded-project-workflow" in ui, "UI prompt does not identify the skill")
    for key in ("display_name", "short_description", "default_prompt"):
        need(re.search(rf'(?m)^  {key}: ".+"$', ui) is not None, f"Missing UI field {key}")
    for name in names:
        raw = source_path(root, name).read_bytes()
        try:
            content = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidRelease(f"Unexpected non-UTF-8 public source: {name}") from exc
        need(PERSONAL_PATH.search(content) is None, f"Machine-specific absolute path: {name}")
        if name.endswith(".py"):
            try:
                ast.parse(content, filename=name)
            except SyntaxError as exc:
                raise InvalidRelease(f"Python syntax error: {name}: {exc.lineno}") from exc
        if not name.endswith(".md"):
            continue
        for match in MARKDOWN_LINK.finditer(content):
            target = match.group(1).strip().strip("<>")
            if target.startswith("#") or urlsplit(target).scheme:
                continue
            target = unquote(target.split("#", 1)[0].split("?", 1)[0])
            if not target:
                continue
            linked = (root / name).parent / target
            need(linked.resolve().is_relative_to(root.resolve()), f"External local link: {name}: {target}")
            need(linked.exists(), f"Broken local link: {name}: {target}")
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    need("MIT License" in license_text and "Copyright (c) 2026 YuWYY" in license_text,
         "Original work license or attribution missing")


def make_manifest(root: Path, names: list[str]) -> dict:
    records = {}
    for name in names:
        data = source_path(root, name).read_bytes()
        records[name] = {"sha256": digest(data), "bytes": len(data)}
    return {"schema": 1, "version": VERSION, "files": records}


def check_sources(root: Path) -> list[str]:
    names = listed_sources(root)
    expected = set(names) | {MANIFEST}
    actual = actual_sources(root)
    need(actual == expected, f"Source inventory mismatch; extra={sorted(actual - expected)}, missing={sorted(expected - actual)}")
    semantic_checks(root, names)
    return names


def validate(root: Path) -> list[str]:
    names = check_sources(root)
    try:
        saved = json.loads((root / MANIFEST).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InvalidRelease(f"Cannot read {MANIFEST}: {exc}") from exc
    actual = make_manifest(root, names)
    if saved != actual:
        previous = saved.get("files", {})
        changed = [name for name, record in actual["files"].items() if previous.get(name) != record]
        raise InvalidRelease(f"Manifest mismatch: {changed or 'schema/version/file inventory'}")
    return names


def refresh_manifest(root: Path) -> None:
    names = listed_sources(root)
    need(actual_sources(root) <= set(names) | {MANIFEST}, "Unlisted source files; update the allowlist explicitly")
    semantic_checks(root, names)
    output = json.dumps(make_manifest(root, names), ensure_ascii=False, indent=2) + "\n"
    (root / MANIFEST).write_text(output, encoding="utf-8", newline="\n")


def package_contents(root: Path, names: list[str]) -> dict[str, dict[str, bytes]]:
    skill_files = {"embedded-project-workflow/" + name[len(SKILL) + 1:]: (root / name).read_bytes()
                   for name in names if name.startswith(SKILL + "/")}
    example_files = {"vivado/" + name[len("examples/vivado/"):]: (root / name).read_bytes()
                     for name in names if name.startswith("examples/vivado/")}
    source_files = {"embedded-project-workflow/" + name: (root / name).read_bytes()
                    for name in [*names, MANIFEST]}
    need(bool(example_files), "No Vivado example sources")
    license_data = (root / "LICENSE").read_bytes()
    skill_files["embedded-project-workflow/LICENSE"] = license_data
    example_files["vivado/LICENSE"] = license_data
    return {f"embedded-project-workflow-v{VERSION}.zip": skill_files,
            f"vivado-examples-v{VERSION}.zip": example_files,
            f"embedded-project-workflow-source-v{VERSION}.zip": source_files}


def pack(root: Path) -> None:
    names = validate(root)
    output = root / "dist"
    output.mkdir(exist_ok=True)
    checksums = []
    for name, entries in package_contents(root, names).items():
        destination = output / name
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for member, data in sorted(entries.items()):
                info = zipfile.ZipInfo(member, date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.create_system = 3
                archive.writestr(info, data)
        checksums.append(f"{digest(destination.read_bytes())}  {name}")
    (output / "SHA256SUMS.txt").write_text("\n".join(checksums) + "\n", encoding="ascii", newline="\n")


def verify_packages(root: Path) -> None:
    names = validate(root)
    checksums = []
    for name, entries in package_contents(root, names).items():
        destination = root / "dist" / name
        need(destination.is_file(), f"Missing archive: {name}")
        with zipfile.ZipFile(destination) as archive:
            need(archive.testzip() is None, f"Archive CRC failure: {name}")
            members = archive.namelist()
            need(len(members) == len(set(members)) and set(members) == set(entries), f"Archive inventory mismatch: {name}")
            for member, data in entries.items():
                need(archive.read(member) == data, f"Archive content mismatch: {name}: {member}")
        checksums.append(f"{digest(destination.read_bytes())}  {name}")
    actual = (root / "dist" / "SHA256SUMS.txt").read_text(encoding="ascii")
    need(actual == "\n".join(checksums) + "\n", "Archive SHA256SUMS mismatch")


def expect_failure(action, message_fragment: str) -> None:
    try:
        action()
    except InvalidRelease as exc:
        need(message_fragment in str(exc), f"Negative case failed for wrong reason: {exc}")
    else:
        raise InvalidRelease(f"Negative case unexpectedly passed: {message_fragment}")


def self_test(root: Path) -> None:
    names = validate(root)
    scratch = root / ".cache"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="release-negative-", dir=scratch) as temporary:
        copy = Path(temporary)
        for name in [*names, MANIFEST]:
            destination = copy / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, destination)
        target = copy / "README.md"
        original = target.read_bytes()
        target.write_bytes(original + b"\nControlled content change.\n")
        expect_failure(lambda: validate(copy), "Manifest mismatch")
        process = subprocess.run(
            [sys.executable, "-B", str(copy / "scripts" / "release.py"), "validate"],
            cwd=copy, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        need(process.returncode == 1 and "Manifest mismatch" in process.stderr,
             "Changed source must make the real CLI exit 1 for its manifest mismatch")
        target.write_bytes(original)
        extra = copy / "unreviewed-source.txt"
        extra.write_text("controlled extra source", encoding="utf-8")
        expect_failure(lambda: validate(copy), "Source inventory mismatch")
        extra.unlink()
        pack(copy)
        verify_packages(copy)
        originals = {name: (copy / "dist" / name).read_bytes()
                     for name in package_contents(copy, names)}
        pack(copy)
        need(all((copy / "dist" / name).read_bytes() == data for name, data in originals.items()),
             "Repeated packaging changed archive bytes")
        for name, entries in package_contents(copy, names).items():
            archive_path = copy / "dist" / name
            original_archive = originals[name]
            member = (f"embedded-project-workflow/{MANIFEST}"
                      if "-source-v" in name else sorted(entries)[0])
            try:
                with zipfile.ZipFile(archive_path, "a") as archive:
                    archive.writestr("unreviewed.txt", "controlled extra archive entry")
                expect_failure(lambda: verify_packages(copy), f"Archive inventory mismatch: {name}")
                archive_path.write_bytes(original_archive)

                with zipfile.ZipFile(archive_path, "w") as archive:
                    for item, data in entries.items():
                        if item != member:
                            archive.writestr(item, data)
                expect_failure(lambda: verify_packages(copy), f"Archive inventory mismatch: {name}")
                archive_path.write_bytes(original_archive)

                with zipfile.ZipFile(archive_path, "w") as archive:
                    for item, data in entries.items():
                        archive.writestr(item, data + b"\nchanged" if item == member else data)
                expect_failure(lambda: verify_packages(copy), f"Archive content mismatch: {name}: {member}")
                archive_path.write_bytes(original_archive)

                # Contents and CRC remain valid, but the saved checksum belongs to the old ZIP.
                with zipfile.ZipFile(archive_path, "a") as archive:
                    archive.comment = b"Controlled changed archive metadata"
                expect_failure(lambda: verify_packages(copy), "Archive SHA256SUMS mismatch")
                archive_path.write_bytes(original_archive)

                archive_path.unlink()
                expect_failure(lambda: verify_packages(copy), f"Missing archive: {name}")
            finally:
                archive_path.write_bytes(original_archive)
            print(f"PASS: {name}: extra/missing member, changed data, stale checksum and missing ZIP rejected")
        verify_packages(copy)
        with tempfile.TemporaryDirectory(prefix="source-", dir=scratch) as source_temporary:
            unpacked = Path(source_temporary)
            with zipfile.ZipFile(copy / "dist" / f"embedded-project-workflow-source-v{VERSION}.zip") as archive:
                # Remove only the checked archive wrapper to avoid another long Windows path level.
                prefix = "embedded-project-workflow/"
                for member in archive.namelist():
                    need(member.startswith(prefix), f"Unexpected source archive prefix: {member}")
                    target = source_path(unpacked, member[len(prefix):])
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(member))
            process = subprocess.run(
                [sys.executable, "-B", str(unpacked / "scripts" / "release.py"), "validate"],
                cwd=unpacked, capture_output=True, encoding="utf-8", errors="replace", check=False,
            )
            need(process.returncode == 0 and "PASS: validate" in process.stdout,
                 f"Extracted source archive failed its own validation: {process.stderr}")
    print("PASS: source mutations rejected; three deterministic archives verified, including extracted source CLI")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["validate", "refresh-manifest", "pack", "verify-packages", "self-test"])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    actions = {"validate": validate, "refresh-manifest": refresh_manifest, "pack": pack,
               "verify-packages": verify_packages, "self-test": self_test}
    try:
        actions[args.command](root)
    except (InvalidRelease, OSError, zipfile.BadZipFile) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(f"PASS: {args.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
