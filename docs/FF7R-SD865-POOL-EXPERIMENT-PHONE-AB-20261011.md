# FFVII Remake / S20+ — DXVK 2.7.1 isolated 64/32 MiB pool experiment

**Status: experimental, not a confirmed fix.** This WCP is independent of the earlier diagnostic WCP. The project uses FEX2610, Turnip T30 / PurpleVK, the Snapdragon 865 / Adreno 650, and GameNative. Real Turnip OOM was already established by repeated `VK_ERROR_OUT_OF_DEVICE_MEMORY` returns in the preceding device logs.

## Precisely scoped implementation

Source: `src/dxvk/dxvk_memory.cpp`, compile flag `DXVK_SD865_POOL_WCP=1` controlled by `package-release.sh`. Builds are separate GameNative `DXVK` packages `ff7r-pool64m32m-dxvk271-<commit>.wcp` containing x32 and x64 DXVK DLLs. The runtime gate `DXVK_SD865_POOL_EXPERIMENT=1` is **required to enable** experimental behavior. When not enabled, the selected WCP follows normal DXVK pool sizing, normal empty retention and original Vulkan allocation/ retry policy.

When enabled:
- **Device pool maximum** 64 MiB vs 256 MiB ordinary setting.
- **Mapped pool maximum** 32 MiB vs 64 MiB on 64-bit platforms, retaining smaller 32-bit defaults.
- The `HOST_VISIBLE | DEVICE_LOCAL` (HVV) special path cannot widen `maxChunkSize` beyond the mapped-pool cap. This matters because otherwise the actual 256 → 128 → 64 MiB fallback would persist.
- **Completely empty chunks** (`pagesUsed(i) == 0`) are eligible to be freed immediately; occupied chunks, resource addresses, existing page-mapping and buffer-device-address flags are untouched.
- Log `DXVK-SD865-POOL state=init enabled=<0|1>` at startup, and extend existing `stage=driver_retry`/`stage=pool_exhausted` failure-only logs with `pool_experiment=<0|1>`, `empty_chunks_reclaimed`, `empty_bytes_reclaimed`. Diagnostic logging is bounded at 128 events per process plus bootstrap markers.
- **Does not** spoof Vulkan `memoryHeaps[].size`, raise budget numbers, disable BDA, force untested Vulkan capabilities, or change memory-type selection and retry results.

## Install and compare, all on the phone (no ADB)

Download the successful CI artifact from [FF7R pool WCP workflow](https://github.com/Ragnarok93/dxvk-SD865/actions/workflows/ff7r-pool-64m-32m-dxvk271-wcp.yml). GitHub wraps artifacts in ZIP; extract the inner `.wcp` and import that file into **GameNative → Contents Manager → DXVK**, then select it as the **DXVK Version** for FFVII Remake. It is not a graphics-driver/Wrappper update. Keep the proven ordinary DXVK 2.7.1 or previous diagnostic WCP for rollback.

For both A/B runs, keep GameNative **Graphics → Max Device Memory = 0 MB** (no Vulkan heap override), unchanged FEX2610, Turnip T30 / PurpleVK, resolution, graphics preset, Wine/Proton version, and any DXVK_CONFIG settings. Keep LSFG and vkBasalt off for a consistent baseline. Avoid Wine `+vulkan` tracing (gigantic logs).

**Run A — unchanged allocator policy in the same WCP** (the control):

```ini
DXVK_SD865_POOL_EXPERIMENT=0
DXVK_SD865_ALLOC_TRACE=1
DXVK_LOG_LEVEL=error
```

After launching, look for `DXVK-SD865-POOL state=init enabled=0`. Reproduce FF7R memory failure. Export GameNative's **Settings → Debug → View game debug log → Save**, and `ff7remake__d3d11.log` if available.

**Run B — only change the opt-in flag**, then fully stop/restart the container/game:

```ini
DXVK_SD865_POOL_EXPERIMENT=1
DXVK_SD865_ALLOC_TRACE=1
DXVK_LOG_LEVEL=error
```

Look for `DXVK-SD865-POOL state=init enabled=1`. Export the same logs at the comparable scene, ideally using the exact same FF7R save/load path. Upload Run A and B. Once testing is over, remove the pool variable or return to ordinary DXVK 2.7.1.

## Success / failure criteria

**Improvement:** Lower DXVK `memoryAllocated - memoryUsed` slack and/or later first unrecovered `VK_ERROR_OUT_OF_DEVICE_MEMORY`, at matched game load and progression, or stable game progression that previously failed. Keep an eye on load time, allocation thrashing, freezes and visual correctness. A few reclaimed empty chunks alone **do not** prove the driver OOM is fixed.

**No improvement:** Real driver OOM remains at roughly 3.9–4.0 GiB DXVK allocated even with reduced pool size and positive reclamation counters. That would suggest live GPU BO/address-space pressure or fragmentation beyond fully empty DXVK chunks and motivate direct Turnip/driver memory-pressure analysis.

**Do not compare raw diagnostic record counts** without matched run conditions; trace events cap at 128, and the first failing 256-MiB vs 64-MiB chunks differ by policy.

This source has Python contract/regression tests and a GitHub Actions PE x64/x32 CI build with static binary marker verification. Compilation is NOT proof of successful runtime on the S20+; user device evidence is needed.
