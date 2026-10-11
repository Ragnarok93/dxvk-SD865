#!/usr/bin/env python3
"""Classify an FF7 Remake Phase-0 DXVK/FEX session without guessing the API.

Input logs must come from ONE launch. A first DXGI present is not the same as
a confirmed display scan-out or a native frame-time measurement.
"""
import argparse
import json
import re
from pathlib import Path

GAME_EXE = "ff7remake_.exe"
DEVICE = re.compile(r"DXVK-FF7R-PHASE0: d3d11_device_created exe=(\S+) feature_level=(\S+)", re.I)
PRESENT = re.compile(r"DXVK-FF7R-PHASE0: first_dxgi_present exe=(\S+) d3d12_queue=([01]) sync_interval=(\d+)", re.I)
FEX = re.compile(r"FEX-FF7R-PHASE0: backend=(ARM64EC|WoW64) app=(\S+) pid=(\d+) wine=([01])", re.I)
DXVK_GAME = re.compile(r"\bGame:\s*(\S+)", re.I)
DXVK_VERSION = re.compile(r"\bDXVK:\s*(\d+\.\d+(?:\.\d+)?)", re.I)
REJECTED_FEATURE = re.compile(r"Skipping:\s*Device does not support required feature ['\"]([^'\"\r\n]+)['\"]", re.I)
DXVK_FAILURE = re.compile(r"Failed to initialize DXVK", re.I)
FEX_ARM64EC_DLL = re.compile(r"Loaded\s+L\"[^\"]*\\libarm64ecfex\.dll\"", re.I)
FEX_WOW64_DLL = re.compile(r"Loaded\s+L\"[^\"]*\\libwow64fex\.dll\"", re.I)
WINE_D3D11_DLL = re.compile(r"Loaded\s+L\"[^\"]*\\d3d11\.dll\"", re.I)
WINE_D3D12_DLL = re.compile(r"Loaded\s+L\"[^\"]*\\d3d12\.dll\"", re.I)


def is_game(exe):
    return exe.replace("\\", "/").rsplit("/", 1)[-1].lower() == GAME_EXE


def classify(lines):
    devices = []
    presents = []
    translators = []
    dxvk_games = set()
    dxvk_versions = set()
    rejected_features = set()
    dxvk_failed = False
    arm64ec_dll_events = 0
    wow64_dll_events = 0
    d3d11_dll_events = 0
    d3d12_dll_events = 0
    for line in lines:
        game_match = DXVK_GAME.search(line)
        if game_match and is_game(game_match.group(1)):
            dxvk_games.add(GAME_EXE)
        version_match = DXVK_VERSION.search(line)
        if version_match:
            dxvk_versions.add(version_match.group(1))
        rejected_match = REJECTED_FEATURE.search(line)
        if rejected_match:
            rejected_features.add(rejected_match.group(1))
        dxvk_failed |= bool(DXVK_FAILURE.search(line))
        arm64ec_dll_events += bool(FEX_ARM64EC_DLL.search(line))
        wow64_dll_events += bool(FEX_WOW64_DLL.search(line))
        d3d11_dll_events += bool(WINE_D3D11_DLL.search(line))
        d3d12_dll_events += bool(WINE_D3D12_DLL.search(line))
        match = DEVICE.search(line)
        if match and is_game(match.group(1)):
            devices.append(match.group(2))
        match = PRESENT.search(line)
        if match and is_game(match.group(1)):
            presents.append({"d3d12_queue": match.group(2) == "1",
                             "sync_interval": int(match.group(3))})
        match = FEX.search(line)
        if match and is_game(match.group(2)):
            translators.append({"backend": match.group(1).upper(),
                                "wine": match.group(4) == "1"})

    queue_types = {p["d3d12_queue"] for p in presents}
    if len(queue_types) > 1:
        api = "mixed_or_ambiguous"
    elif queue_types == {True}:
        api = "d3d12_dxgi_present_path"
    elif queue_types == {False} and devices:
        api = "d3d11_dxvk_present_path"
    elif queue_types == {False}:
        api = "dxgi_present_no_d3d11_device_evidence"
    elif devices:
        api = "d3d11_device_only_no_present"
    elif dxvk_games and rejected_features and dxvk_failed:
        api = "dxvk_adapter_rejected_before_present"
    else:
        api = "unverified"

    warnings = []
    if not presents:
        warnings.append("No successful DXGI Present observed; do not infer rendering API from DLL loading.")
    if presents and not devices and queue_types == {False}:
        warnings.append("DXGI Present without DXVK D3D11 device marker; another API may own rendering.")
    if len(queue_types) > 1:
        warnings.append("Mixed presentation paths: separate process/session logs before analysis.")
    if not translators:
        warnings.append("No FEX Phase-0 process marker. Logging may be suppressed or the probe may not be loaded.")
    if dxvk_games and rejected_features and dxvk_failed:
        warnings.append("DXVK rejected the Vulkan adapter before rendering; this does not establish a D3D11 feature-level bug.")
    if arm64ec_dll_events and not translators:
        warnings.append("Wine loaded libarm64ecfex.dll, but the instrumented FEX version and startup marker remain unverified.")
    if d3d11_dll_events and not devices:
        warnings.append("A native d3d11.dll was loaded, but successful D3D11 device creation is not established.")
    warnings.append("DXGI Present success does not establish on-screen display timing or real FPS.")
    return {
        "api_evidence": api,
        "dxvk_versions_in_logs": sorted(dxvk_versions),
        "dxvk_adapter_missing_features": sorted(rejected_features) if dxvk_games else [],
        "dxvk_initialization_failed": bool(dxvk_games and dxvk_failed),
        "wine_arm64ec_fex_load_events": arm64ec_dll_events,
        "wine_wow64_fex_load_events": wow64_dll_events,
        "wine_d3d11_dll_load_events": d3d11_dll_events,
        "wine_d3d12_dll_load_events": d3d12_dll_events,
        "d3d11_device_events": len(devices),
        "d3d11_feature_levels": sorted(set(devices)),
        "dxgi_first_present_events": len(presents),
        "dxgi_d3d12_queue_events": sum(p["d3d12_queue"] for p in presents),
        "fex_backends": sorted({t["backend"] for t in translators}),
        "fex_wine_processes": sum(t["wine"] for t in translators),
        "warnings": warnings,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", type=Path, help="DXVK, FEX or GameNative text logs from one session")
    parser.add_argument("--json-out", type=Path, help="Write a portable, path-free JSON report")
    parser.add_argument("--require-api", choices=["d3d11", "d3d12"],
                        help="Exit nonzero unless this DXGI rendering path was observed")
    args = parser.parse_args(argv)
    def session_lines():
        for path in args.logs:
            if not path.is_file():
                parser.error(f"Log does not exist: {path}")
            with path.open(encoding="utf-8", errors="replace") as stream:
                yield from stream

    report = classify(session_lines())
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(payload, end="")
    if args.json_out:
        args.json_out.write_text(payload, encoding="utf-8")
    expected = {"d3d11": "d3d11_dxvk_present_path", "d3d12": "d3d12_dxgi_present_path"}
    return 2 if args.require_api and report["api_evidence"] != expected[args.require_api] else 0


if __name__ == "__main__":
    raise SystemExit(main())
