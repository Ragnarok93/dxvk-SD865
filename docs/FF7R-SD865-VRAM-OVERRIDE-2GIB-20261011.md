# FFVII Remake S20+ — Latest captured 2-GiB Vulkan heap override with ongoing driver OOM

**Evidence date:** 2026-10-11 23:25 UTC. Source user uploads: `ff7remake__d3d11.log` (152 lines), `ff7remake__dxgi.log` (4 lines), `wine_debug.log (4).txt` (856 lines), and *old* `pluvia_crash_2026-10-06_06-51-57 (2).txt`. Original private device logs intentionally not committed.

## Measured, not inferred

The new D3D11 log has **128 opt-in `DXVK-SD865-ALLOC` events (bounded log cap)** consisting of **105 `driver_retry`** and **23 `pool_exhausted`**. All 105 have `first_vkresult=-2 retry_vkresult=-2 recovered=0` -> real driver `VK_ERROR_OUT_OF_DEVICE_MEMORY`, including retry. These failed calls have `flags=2` (buffer device address), `dedicated=0`, `buffer_usage=137727`, device heap 0. Failed chunks span 16, 32, 64, 128, 256 MiB and eligible types 0/1/2. The 128-event cap means **105 failures is an observed lower bound, not a count of all driver rejections or directly comparable with the earlier run's 18**.

- First logged failure: `dxvk_allocated_bytes=3976200192` = **3792 MiB**, `dxvk_used_bytes=3740710144` ~3567.4 MiB.
- Last logged failure: `dxvk_allocated_bytes=4160749568` = **3968 MiB**, `dxvk_used_bytes=3905003264` ~3724.1 MiB, allocated-unused slack ~243.9 MiB.
- All events report `dxvk_budget_bytes=2126008812` = **2027.52 MiB**. DXVK memory-summary lines report **heap size 2048 MiB**, allocated 3968 MiB, driver-reported heap budget ~4306-4418 MiB. This is a **new 2-GiB driver-facing heap-size report**, compared with **7951 MiB** in the previous capture. It did not constrain the actual DXVK allocated total to 2 GiB. The source DXVK UMA path does not enforce the normal discrete-GPU budget guard.
- Terminal errors are DXVK `Memory allocation failed` for multiple `~11.2/22.4` million-byte requests; associated Wine debug crash helper, critical section stalls and X-server disconnect occur later. The D3D11 log does not identify an exact native crash stack.
- The DXGI log only reports fallback EDID parsing.
- Uploaded October 6 `pluvia_crash` is *again* the old GameNative `GPUImage.isHardwareBufferConfigurationSupported` JNI symbol-linkage exception, **not** current FF7R driver OOM. Do not conflate or use it as current driver evidence.

## Source explanation: three different kinds of 'VRAM limit'

**1) DXGI reported dedicated VRAM:** `src/dxgi/dxgi_options.cpp:90` reads config key `dxgi.maxDeviceMemory` using `config.getOption`, and `src/dxgi/dxgi_adapter.cpp:480-482` clamps **DXGI adapter-desc `deviceMemory`**, not Vulkan `VkPhysicalDeviceMemoryProperties.memoryHeaps[i].size`. A standalone GameNative environment variable named `dxgi.maxDeviceMemory` is ignored by DXVK. Correct env name `DXVK_CONFIG`, value `dxgi.maxDeviceMemory = 3072` (or file-based `dxvk.conf`). Existing error-only DXVK logs cannot prove whether that config was parsed; temporarily enable INFO logging or add a one-time effective-config probe.

**2) Wrapper Vulkan memory heap-size spoof:** The pinned research wrapper source `leegao/mesa-wrapper-CI/src/vulkan/wrapper/wrapper_physical_device.c:930-959` implements `WRAPPER_VMEM_MAX_SIZE` via `getenv/atoi`, and if positive **overwrites raw Vulkan heap 0 .size** in both `vkGetPhysicalDeviceMemoryProperties` and `vkGetPhysicalDeviceMemoryProperties2`. Setting `WRAPPER_VMEM_MAX_SIZE=2048` would **exactly produce** a 2048 MiB Vulkan heap report, while the forwarded `VK_EXT_memory_budget` pNext fields can still show >4 GiB. **This is a strong candidate, not verified from this log** because no active environment dump or one-time raw-versus-wrapper heap diagnostic is present. Verify whether the user's actual installed wrapper and env reflect this source; don't assume they necessarily do.

**3) DXVK allocator internal budget:** `src/dxvk/dxvk_memory.cpp` initializes heap budget to the reported Vulkan heap size; `updateMemoryHeapBudgets` clamps it to `min(driver budget minus internal, heap size)`, with ~1% reserved for device-local heap. `2048 MiB - 1% = 2027.52 MiB` exactly matches `dxvk_budget_bytes=2126008812`. Because this A650 Vulkan device is unified memory architecture, `heap.enforceBudget` is false and further Vulkan calls can accumulate **>2 GiB** despite this planning budget. Thus **the 2048-MiB reported heap cap demonstrably does not function as a physical allocation ceiling**.

**Separate other possibility:** GameNative source only populates `TU_OVERRIDE_HEAP_SIZE=4096` in a Zink path, not its ordinary Turnip/Wrapper FF7R path. Other driver or wrapper heap overrides are possible and require checking current container variables/driver build. A standalone `dxgi.maxDeviceMemory=3072` env var would not directly produce the 2048-MiB Vulkan report.

## Next controlled phone-only A/B (no ADB)

1. In GameNative container environment editor, **check and remove `WRAPPER_VMEM_MAX_SIZE`** if present, especially `2048`; also check for `TU_OVERRIDE_HEAP_SIZE` or other Vulkan heap-overriding switches. Changing the Vulkan heap-size advertisement while leaving budget pNext unchanged is misleading and may upset DXVK memory-pool policy. Don't simply raise fake Vulkan heaps to 8 GiB.
2. Set correct variable **Name `DXVK_CONFIG`**, **Value `dxgi.maxDeviceMemory = 3072`**; preserve/append any existing DXVK_CONFIG content with `; ...`. Retain `DXVK_SD865_ALLOC_TRACE=1`, `DXVK_LOG_LEVEL=error`, and baseline T30/FEX/DXVK; no verbose `+vulkan` Wine traces.
3. Run game once, export D3D11 + Wine logs via GameNative's UI. Without the Vulkan spoof, expect heap advertised back near original ~7951 MiB *if underlying driver and wrapper match prior captures*. This alone may improve allocator bookkeeping; it is not proof that Turnip will stop rejecting allocations.
4. To **verify DXGI cap actually parsed**, temporarily enable `DXVK_LOG_LEVEL=info`, look for `Found config env: dxgi.maxDeviceMemory = 3072` in D3D11/DXGI logs, then restore error-level logging. Or add a single error-level `DXVK-SD865-ALLOC config...` capture to the next build. Don't infer configuration from failed OOM.
5. A later *experimental* WCP can reduce global/mappable DXVK pool chunk size and empty-chunk retention without ever disabling required Vulkan buffer device addresses, and should A/B track minimum rejected chunk, OOM memory level, game progression and visual correctness.

**Code state:** This document is diagnosis only. No Vulkan heap spoof changes, allocator mitigation patches, or new runtime WCP have been applied from this upload. Do not present a new build without successful CI and on-device validation.
