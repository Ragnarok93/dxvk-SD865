#!/usr/bin/env python3
"""Summarize opt-in DXVK-SD865 diagnostics without third-party dependencies.

Counters are over *present requests*, not physical frames. The shader compilation
CPU durations can overlap on multiple threads. Missing final totals are expected
after a crash or hard termination.
"""
import argparse
import json
import re
from pathlib import Path

WINDOW_RE = re.compile(r"DXVK-SD865 counters over (\\d+) present requests: (.*)")
SAMPLE_RE = re.compile(r"DXVK-SD865 compiler sample: (.*)")
TOTAL_RE = re.compile(r"DXVK-SD865 compiler totals: (.*)")
PAIR_RE = re.compile(r"([a-zA-Z][a-zA-Z0-9]*)=(\\d+(?:/\\d+)?)")
COLUMNS = (
    "renderPasses", "barriers", "draws", "dispatches", "submits",
    "gpuSyncs", "gpuWaitUs", "csWaitUs",
)


def pairs(text):
    """Return values with integer types, preserving done/total pairs as dicts."""
    values = {}
    for match in PAIR_RE.finditer(text):
        value = match.group(2)
        if "/" in value:
            done, total = value.split("/", 1)
            values[match.group(1)] = {"completed": int(done), "total": int(total)}
        else:
            values[match.group(1)] = int(value)
    return values


def summarize(lines):
    totals = {key: 0 for key in COLUMNS}
    presents = 0
    windows = 0
    last_shader_tasks = None
    last_compiler_sample = None
    final_compiler_totals = None

    for line in lines:
        match = WINDOW_RE.search(line)
        if match:
            interval = int(match.group(1))
            fields = pairs(match.group(2))
            if not interval:
                continue
            presents += interval
            windows += 1
            for key in COLUMNS:
                totals[key] += fields.get(key, 0)
            last_shader_tasks = fields.get("shaderTasks", last_shader_tasks)
            continue
        match = SAMPLE_RE.search(line)
        if match:
            last_compiler_sample = pairs(match.group(1))
            continue
        match = TOTAL_RE.search(line)
        if match:
            final_compiler_totals = pairs(match.group(1))

    if not (windows or last_compiler_sample or final_compiler_totals):
        raise ValueError("No DXVK-SD865 profiling records found (enable profiling first)")

    return {
        "windowCount": windows,
        "presentRequests": presents,
        "totals": totals,
        "perPresent": {
            key: round(value / presents, 6) for key, value in totals.items()
        } if presents else {},
        "latestShaderTasks": last_shader_tasks,
        "latestCompilerSample": last_compiler_sample,
        "finalCompilerTotals": final_compiler_totals,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logfile", type=Path, help="DXVK or Wine log file")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args()
    with args.logfile.open("r", encoding="utf-8", errors="replace") as fp:
        try:
            data = summarize(fp)
        except ValueError as error:
            parser.error(str(error))

    if args.json:
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(f"SD865 telemetry: {data['windowCount']} windows, {data['presentRequests']} CPU present requests")
        for key, value in data["totals"].items():
            rate = data["perPresent"].get(key, 0.0)
            print(f"  {key}: {value} total, {rate:.3f} per present")
        if data["latestCompilerSample"]:
            print("  Last compiler sample:", data["latestCompilerSample"])
        if data["finalCompilerTotals"]:
            print("  Final compiler totals:", data["finalCompilerTotals"])


if __name__ == "__main__":
    main()
