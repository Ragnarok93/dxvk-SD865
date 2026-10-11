#!/usr/bin/env python3
"""Classify opt-in DXVK-SD865 Vulkan allocation failures from GameNative log exports.

No root, ADB or external Python packages required. Accepts arbitrary Wine/DXVK text
and emits a JSON summary, preserving exact VkResult codes without inference.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path

MARKER = "DXVK-SD865-ALLOC stage="
KV = re.compile(r"([a-z][a-z0-9_]*)=([^\s]+)", re.IGNORECASE)
STAGES = {"driver_retry", "budget_guard", "pool_exhausted", "dedicated_exhausted"}
RESULTS = {
    "VK_SUCCESS", "VK_ERROR_OUT_OF_HOST_MEMORY", "VK_ERROR_OUT_OF_DEVICE_MEMORY",
    "VK_ERROR_TOO_MANY_OBJECTS", "VK_ERROR_INITIALIZATION_FAILED",
    "VK_ERROR_UNKNOWN", "OTHER_VK_RESULT",
}


def summarize(lines):
    events = []
    reasons = Counter()
    outcomes = Counter()
    for line in lines:
        pos = line.find(MARKER)
        if pos < 0:
            continue
        data = dict(KV.findall(line[pos:]))
        stage = data.get("stage")
        if stage not in STAGES:
            continue
        safe = {"stage": stage}
        for field in (
            "first_vkresult", "retry_vkresult", "recovered",
            "first_attempt_id", "retry_attempt_id",
            "requested_bytes", "memory_type", "heap", "heap_size_bytes", "dedicated",
            "dxvk_allocated_bytes", "dxvk_used_bytes", "dxvk_budget_bytes",
            "driver_allocated_bytes", "driver_budget_bytes",
            "pool_experiment", "empty_chunks_reclaimed", "empty_bytes_reclaimed",
            "flags", "buffer_usage", "driver_call",
            "requested_memory_types_mask", "eligible_memory_types_mask",
            "property_flags", "alignment", "has_dedicated_info",
            "no_allocation_mode",
        ):
            if field in data:
                try:
                    safe[field] = int(data[field], 0)
                except ValueError:
                    pass
        for field in ("first_name", "retry_name"):
            if data.get(field) in RESULTS:
                safe[field] = data[field]
        events.append(safe)
        reasons[stage] += 1
        if stage == "driver_retry":
            if safe.get("recovered") == 1:
                outcomes["recovered_after_retry"] += 1
            elif safe.get("recovered") == 0:
                outcomes["failed_after_retry"] += 1
            else:
                outcomes["missing_retry_outcome"] += 1
            for field in ("first_name", "retry_name"):
                if field in safe:
                    outcomes[f"{field}:{safe[field]}"] += 1
    missing = not events
    return {
        "status": "no_diagnostic_marker" if missing else "events_found",
        "event_count": len(events),
        "by_stage": dict(sorted(reasons.items())),
        "outcomes": dict(sorted(outcomes.items())),
        "events": events,
        "interpretation_limit": (
            "A Vulkan VkResult identifies a failed allocation attempt, not necessarily "
            "a unique hardware limit, OS kill, final game crash, or overall GPU budget exhaustion."
        ),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("logs", nargs="+", type=Path)
    p.add_argument("--json-out", type=Path)
    args = p.parse_args()

    def lines():
        for path in args.logs:
            with path.open("r", encoding="utf-8", errors="replace") as stream:
                yield from stream

    report = summarize(lines())
    output = json.dumps(report, indent=2) + "\n"
    print(output, end="")
    if args.json_out:
        args.json_out.write_text(output, encoding="utf-8")
    return 0 if report["event_count"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
