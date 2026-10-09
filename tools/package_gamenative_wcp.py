#!/usr/bin/env python3
"""Package DXVK x32/x64 DLLs into GameNative .wcp (tar.zst)."""
import argparse
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath

TRUSTED = ("d3d8.dll", "d3d9.dll", "d3d10.dll", "d3d10_1.dll",
           "d3d10core.dll", "d3d11.dll", "dxgi.dll")
REQUIRED = frozenset(("d3d9.dll", "d3d10core.dll", "d3d11.dll", "dxgi.dll"))


def stage_dxvk(build: Path, stage: Path, version: str) -> dict:
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", version):
        raise ValueError("version must contain only letters, numbers, _, - or .")
    profile = {
        "type": "DXVK",
        "versionName": version,
        "versionCode": 1,
        "description": "dxvk-SD865 experimental Adreno 650 / Mesa Turnip",
        "files": [],
    }
    for arch, target in (("x64", "${system32}"), ("x32", "${syswow64}")):
        folder = build / arch
        if not folder.is_dir():
            raise ValueError(f"Missing DXVK {arch} output folder: {folder}")
        present = {p.name for p in folder.glob("*.dll") if p.is_file()}
        missing = REQUIRED - present
        if missing:
            raise ValueError(f"Missing required {arch} DLLs: {sorted(missing)}")
        (stage / arch).mkdir(parents=True, exist_ok=True)
        for name in TRUSTED:
            if name in present:
                shutil.copyfile(folder / name, stage / arch / name)
                profile["files"].append({
                    "source": f"{arch}/{name}",
                    "target": f"{target}/{name}",
                })
    (stage / "profile.json").write_text(
        json.dumps(profile, indent=2) + "\n", encoding="utf-8")
    return profile


def write_tar(stage: Path, archive: Path) -> None:
    """Write explicit directory entries BEFORE their files.

    GameNative's TarCompressorUtils extracts files using FileOutputStream
    without creating the parent directories. Tar files that omit x32/ and
    x64/ directory records therefore fail with ERROR_BADTAR.
    """
    with tarfile.open(archive, "w", format=tarfile.GNU_FORMAT) as tar:
        # Sorting includes directories before their children, not just files.
        # recursive=False prevents adding directory contents twice.
        for item in sorted(stage.rglob("*")):
            tar.add(item, arcname=item.relative_to(stage).as_posix(),
                    recursive=False)
    validate_gamenative_tar(archive)


def validate_gamenative_tar(archive: Path) -> None:
    """Model GameNative's single-pass tar extraction parent-directory rule."""
    created_dirs = { "." }
    required = { "profile.json", "x32/d3d11.dll", "x64/d3d11.dll",
                 "x32/dxgi.dll", "x64/dxgi.dll" }
    names = set()
    with tarfile.open(archive, "r") as src:
        for item in src:
            name = item.name.rstrip("/")
            path = PurePosixPath(name)
            if not name or path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unsafe tar member: {item.name}")
            parent = path.parent.as_posix()
            if item.isdir():
                if parent not in created_dirs:
                    raise ValueError(f"Missing parent directory for: {name}")
                created_dirs.add(name)
            elif item.isfile():
                if parent not in created_dirs:
                    raise ValueError(f"Missing parent directory entry before {name}")
            else:
                raise ValueError(f"Unexpected tar member type: {name}")
            if name in names:
                raise ValueError(f"Duplicate tar member: {name}")
            names.add(name)
    if not required.issubset(names):
        raise ValueError(f"Incomplete GameNative WCP: {sorted(required - names)}")


def package(build: Path, output: Path, version: str) -> dict:
    if shutil.which("zstd") is None:
        raise RuntimeError("Install zstd before packaging a .wcp")
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="gamenative-wcp-") as tmp:
        folder = Path(tmp)
        stage = folder / "contents"
        stage.mkdir()
        profile = stage_dxvk(build.resolve(), stage, version)
        archive = folder / "archive.tar"
        write_tar(stage, archive)
        subprocess.run(["zstd", "-q", "-19", "-f", "-o",
                        str(output), str(archive)], check=True)
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version-name", required=True)
    args = parser.parse_args()
    manifest = package(args.input, args.output, args.version_name)
    print(f"Created {args.output} ({len(manifest['files'])} DLL entries)")


if __name__ == "__main__":
    main()
