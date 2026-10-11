#!/usr/bin/env python3
"""Fail-closed analysis of FF7R raw Turnip vs wrapper 8-bit-storage log markers.

A positive feature report is not shader correctness or DXVK 3.1.1 compliance.
Use logs from one run, one loaded ICD and one Vulkan physical device.
"""
import argparse
import json
import re
from pathlib import Path

FIELDS = ("storage8", "shaderInt8", "uniform8", "pushConstant8")
MARKER = re.compile(r"FF7R-8BIT:\\s+(.*)")
TOKEN = re.compile(r"\\b(raw|wrapper)_(storage8|shaderInt8|uniform8|pushConstant8)=(\\d+)\\b")
DXVK_MISSING = re.compile(r"Device does not support required feature ['\\\"]([^'\\\"]+)['\\\"]")
DEVICE = re.compile(r"Found device:\\s*(.*)", re.I)


def analyze(lines):
    samples = []
    dxvk_missing = set()
    devices = set()
    for line in lines:
        m = MARKER.search(line)
        if m:
            tokens = {(kind, key): int(value) for kind, key, value in TOKEN.findall(m.group(1))}
            if len(tokens) == 2 * len(FIELDS) and all(v in (0, 1) for v in tokens.values()):
                samples.append({
                    "raw": {key: tokens[("raw", key)] for key in FIELDS},
                    "wrapper": {key: tokens[("wrapper", key)] for key in FIELDS},
                })
        m = DXVK_MISSING.search(line)
        if m:
            dxvk_missing.add(m.group(1))
        m = DEVICE.search(line)
        if m:
            devices.add(m.group(1).strip())

    unique = {json.dumps(s, sort_keys=True) for s in samples}
    if not samples:
        verdict = "no_valid_audit_marker"
    elif len(unique) > 1:
        verdict = "conflicting_driver_or_session_results"
    else:
        sample = samples[0]
        if sample["raw"] != sample["wrapper"]:
            verdict = "raw_wrapper_feature_mismatch"
        elif not sample["raw"]["storage8"]:
            verdict = "driver_reports_storage8_unavailable"
        else:
            verdict = "both_report_storage8_available_not_conformance_proof"

    return {
        "verdict": verdict,
        "marker_count": len(samples),
        "raw_features": samples[0]["raw"] if len(unique) == 1 and samples else None,
        "wrapper_features": samples[0]["wrapper"] if len(unique) == 1 and samples else None,
        "dxvk_rejected_features": sorted(dxvk_missing),
        "observed_devices": sorted(devices),
        "limitations": [
            "Requires a trusted unmodified source, known loaded Turnip ICD and a single-session capture.",
            "Reported features alone do not demonstrate vkCreateDevice success, 8-bit SSBO correctness, or DXVK 3.1.1 compatibility.",
        ],
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("logs", nargs="+", type=Path, help="Wine/wrapper/DXVK logs from one launch")
    p.add_argument("--json-out", type=Path, help="Write JSON audit report")
    args = p.parse_args()
    def lines():
        for log in args.logs:
            with log.open(encoding="utf-8", errors="replace") as handle:
                yield from handle
    report = analyze(lines())
    result = json.dumps(report, indent=2, sort_keys=True) + "\n"
    print(result, end="")
    if args.json_out:
        args.json_out.write_text(result, encoding="utf-8")
    if report["verdict"] in ("no_valid_audit_marker", "conflicting_driver_or_session_results"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
