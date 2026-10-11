# FFVII Remake SD865 — Confirmed Vulkan allocation failure (`VK_ERROR_OUT_OF_DEVICE_MEMORY`)

**Evidence:** User-uploaded `ff7remake__d3d11.log` (16 lines), `ff7remake__dxgi.log` (4 lines), `wine_debug.log (1).txt` (658 lines) provided on 2026-10-11 15:06 UTC. This is a real A650/GameNative device result using **our first diagnostic WCP** (lines do NOT include later `first_attempt_id`, `heap_size_bytes`, startup-marker fields). No raw user logs are committed.

## Confirmed crash-path diagnosis

- **9** `DXVK-SD865-ALLOC stage=driver_retry` events. For **all 9**, `first_vkresult=-2` and `retry_vkresult=-2`, each correctly identifying `VK_ERROR_OUT_OF_DEVICE_MEMORY`. All have `recovered=0`. This verifies Turnip/Vulkan rejected actual `vkAllocateMemory` requests; it is not merely DXVK's own budget guard.
- **1** `stage=pool_exhausted`: game requests **22,369,792 bytes (~21.33 MiB)**, alignment 256, `requested_memory_types_mask=7` (types 0/1/2), `eligible_memory_types_mask=3` (types **0/1**), `property_flags=6` (`HOST_VISIBLE | HOST_COHERENT`), `no_allocation_mode=0`.
- Vulkan chunks attempted, including retries per attempt:
  - 256 MiB @ type 0; 128 MiB @ type 0; 64 MiB @ type 0;
  - 256 MiB @ type 0; 128 MiB @ type 0; 64 MiB @ type 0;
  - 64 MiB @ type 0; 32 MiB @ type 0; 32 MiB @ type 1.
- **All nine failures** are `dedicated=0`, `flags=2` (**`VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT`**), `buffer_usage=137727`. These are *global pooled buffer* Vulkan allocations requiring a buffer device address, not dedicated texture/image allocation. There is not yet evidence that the device-address flag is the direct cause; it is a critical discriminant for further A/B.
- At final failure DXVK prints memory heap 0 `Size=7951 MiB, Allocated=4004 MiB, Used=3781 MiB, Reserved=3785 MiB, Budget=4798 MiB`. The error-level diagnostic printed `dxvk_allocated_bytes=4198498304` = **4004 MiB**, `dxvk_used_bytes=3965190656` = **3781.5 MiB**, while `driver_budget_bytes~5032e6` = **~4798 MiB**. Thus ~222.5 MiB DXVK allocated-but-not-used and ~794 MiB below the published budget at failure. The new run does **not** reproduce the **4096 MiB enumerated heap** of the older capture; the earlier analysis must not elevate that to a fixed reported heap limit.
- Final Wine trace sequence lines ~541-556 contains the same 9 failures, pool exhaustion and DXVK heap snapshot; diagnostics then print Wine debug-symbol warnings, `RtlpWaitForCriticalSection ... wait timed out` around line 629, and X server disconnect lines 648+. These events establish a failure and teardown but no conclusive native backtrace; no command-stream exception is shown **in this capture**.
- DXGI log shows EDID/colorimetry fallback only. The `pluvia_crash_2026-10-06_06-51-57.txt` is a **separate historical** Android JNI `UnsatisfiedLinkError`, unrelated to this specific game's Vulkan driver OOM event.
- Unlike the million-line trace of earlier runs, the exported Wine log is ~64 kB and the D3D11 log ~4 kB. The failure-only diagnostics function and are accessible **without ADB**.

## Root cause confidence table

| Claim | Confidence / status |
|---|---|
| Device driver returned Vulkan OOM (-2), including after retry | **Confirmed** for 9 attempted allocations |
| DXVK unable to service a ~21.33 MiB host-visible, coherent pooled buffer request | **Confirmed** |
| Device-address requirement present in all the failed requests | **Confirmed** |
| DXVK-side `enforceBudget` guard caused these particular rejects | **Ruled out** for the logged driver_retry events |
| Exactly 4-GiB driver/process/Vulkan address-space ceiling | **Unproven**, though DXVK allocation converges near 4 GiB across runs; reported heap is 7951 MiB here |
| Other Android processes, physical-memory pressure, GPU virtual-address fragmentation, kernel IOVA/BO constraints, BDA-specific allocation behavior | **Not isolated** |
| Changing `dxgi.maxDeviceMemory` or allocating smaller global chunks guarantees a fix | **Not supported** |

## Engineering follow-up (no ADB)

1. **Immediate reversible test**: preserve same Turnip+Wrapper+FEX+DXVK and set `dxgi.maxDeviceMemory = 3072` in DXVK config (or adjust to 3584 MiB second test), and set low textures, 540p, LSFG/vkBasalt off. This changes reported DXGI VRAM to encourage **game** streaming but is *not* a Vulkan allocator hard limit. Recheck logged DXVK memory at failure or stability.
2. **A/B experiment with build-only opt-in**: reduce global/mappable *pool chunk size growth* and keep unused chunk retention small. Test smaller chunks and reallocation count versus baseline. This is a plausible way to reduce unused pooled allocation slack of ~222 MiB, **not** a demonstrated fix. Must preserve Vulkan resource usage and BDA semantics and avoid spoofing Vulkan capabilities.
3. If persistent at similar live allocations even with smaller chunks, instrument optional sampling of Android/Turnip allocation pressure and native driver-side error (if exposed via supported APIs). Never modify `VkPhysicalDeviceMemoryProperties` / budgets to claim more physical memory.
4. Consider independent A/B between direct Turnip and PurpleVK and between BDA-required vs truly non-BDA resource paths. **Never suppress device-address allocation flag for a buffer that genuinely needs address support**. Do not implement a global `NO_BDA` shortcut without proving correctness.
5. Improve allocator tracing to log both Vulkan attempts and buffer-pool state/unused pages per failed memory type, and capture the exact configured physical heap size. The latest source already supports attempt ID and heap-size fields. Preserve bounded logging.

See `docs/FF7R-SD865-REPEATABLE-ALLOC-FAILURES-20261011.md` for comparison with prior runs and `docs/FF7R-SD865-ALLOC-TRACE-PHONE-TEST.md` for user-friendly logging.
