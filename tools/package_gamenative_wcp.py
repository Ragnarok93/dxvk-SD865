#!/usr/bin/env python3
"""Package DXVK x32/x64 DLLs into GameNative .wcp (tar.zst)."""
import argparse
import json
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

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
        with tarfile.open(archive, "w") as tar:
            for item in sorted(stage.rglob("*")):
                if item.is_file():
                    tar.add(item, arcname=item.relative_to(stage).as_posix())
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
