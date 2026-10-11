# FFVII Remake on SD865: repeatable Vulkan memory allocation failure

Date 2026-10-11. User supplied two GameNative Wine logs. This is a read-only diagnosis; no runtime driver patch or device validation has been performed beyond the traces the user supplied.

## A/B evidence

| Item | Earlier `wine_debug.log (5).txt` | Latest `wine_debug.log (1).txt` first failure | Latest second failure |
|---|---:|---:|---:|
| Wine log lines | 973,552 | 827,219 (whole newer file) | 827,219 |
| Error line index | 973,299 | 803,173 | 827,052 |
| Allocation request bytes | 22,369,792 | 22,437,888 | 22,369,792 |
| Alignment bytes | 256 | 4096 | 256 |
| Memory types | 0,1,2 | 0,1,2 | 0,1,2 |
| Heap 0 total MiB | 7,951 | 7,951 | 7,951 |
| DXVK allocated MiB | 3,940 | 3,972 | 3,972 |
| DXVK used MiB | 3,734 | 3,686 | 3,737 |
| Vulkan memory-budget extension reported heap reservation MiB | 3,773 | 3,764 | 3,735 |
| Driver budget MiB | 4,520 | 4,792 | 4,775 |
| `thunk64_vkQueuePresentKHR` before error | 3,767 | 3,898 | 3,947 |
| `thunk64_vkAllocateMemory` before error | 53 | 84 | 100 |
| `thunk64_vkFreeMemory` before error | 7 | 7 | 9 |

The log event counts are Wine trace calls, not time-stamped physical frame counts. Both runs produce about **3,800–3,900 presentation calls** before the first allocation failure. The additional new failure occurs just 49 present calls later.

Both logs contain:
```
err:   DxvkMemoryAllocator: Memory allocation failed
err:     Mem types: 0,1,2
```
No usable `VK_ERROR_OUT_OF_DEVICE_MEMORY`, `VK_ERROR_OUT_OF_HOST_MEMORY` or Vulkan return-code trace is printed. The new failure does not depend on the previously observed DXVK minimum-feature-level or maintenance5 adapter rejection: device creation and sustained VK queue submissions and presents precede it.

## What we can and cannot infer

**Strong:** Repeatable failure to obtain a ~21.3-21.4 MiB Vulkan memory allocation near 3.9 GiB of current DXVK allocations; likely a runtime memory/driver/resource failure rather than initial capability mismatch.

**Suggestive, not proven:** A roughly 4-GiB process, driver, memory-accounting, or address-space threshold because allocated memory converges near 3,940–3,972 MiB. Driver-reported overall budget remains >4.5 GiB, so it is not a straightforward exceed-the-published-budget case. Vulkan memory-budget value does not guarantee successful per-object allocation.

**Not established:** (a) exact `VkResult` returned from `vkAllocateMemory`; (b) if a prior DXVK pool-suballocation failure happened without attempted `vkAllocateMemory`; (c) Android/Turnip-specific failure reason, including contiguous DMA / mapping limits, process address-space restrictions, imported Vulkan layer overhead, host allocation exhaustion or 4-GiB limitation; (d) a native crash stack. The Wine `dbghelp_msc Unknown CODEVIEW signature` and X11 connection reset lines occur in shutdown and do not themselves explain the allocation failure. The log contains only unrelated Wine HID `0xc0000005` from service startup, not a FF7R SEH crash stack.

**Important DXVK v2.7.1 implementation behavior:** [`src/dxvk/dxvk_memory.cpp`](https://github.com/doitsujin/dxvk/blob/v2.7.1/src/dxvk/dxvk_memory.cpp) `allocateDeviceMemory` calls `vkAllocateMemory`, frees empty heap chunks and retries if the driver call fails. `enforceBudget` is limited to non-UMA discrete GPUs, not the normal A650 unified-memory path. Hence a DXVK logged failure with allocator/budget below ~5 GB is possible if driver rejects allocation. The log lacks the actual Vulkan error code. `dxgi.maxDeviceMemory` changes VRAM *reported to the game* and may influence streaming; it is NOT a real allocator hard cap or proof of 4 GiB hardware capability.

## Device-only controlled experiment (no ADB)

- Keep DXVK 2.7.1 GPL-async, FEX2610 and Turnip T30 constant.
- Disable LSFG and vkBasalt CAS for baseline, set 540p/lowest textures, 30-FPS limit.
- Disable verbose Wine `+vulkan` and `+loaddll` trace channels but retain GameNative's UI `Enable Wine Debug Logs` and retain DXVK error logging. Both existing logs are >70 MiB and trace millions of calls.
- Launch once and export log through GameNative UI. Determine whether allocation requests still fail near ~3.9 GiB or whether the threshold shifts with texture/resolution, and whether issue reproduces at comparable game progress rather than just present counts.
- Optional diagnostic-only test: set `dxgi.maxDeviceMemory = 3072` in DXVK config to **report** a smaller VRAM amount to FFVII Remake. Measure whether engine streaming reduces actual DXVK allocated footprint. Do not treat this as physical allocation throttling.

## Next DXVK/FEX engineering step if reproducible

Implement a **feature-gated, low-noise failure-only diagnostic in the DXVK-SD865 fork**, not a general per-frame trace: after `vkAllocateMemory` returns non-success, include numeric/symbolic `VkResult`, requested bytes, memory type index and flags, total driver-requested allocation attempt count, DXVK heap allocated/used, current queried `VK_EXT_memory_budget` budget/usage, and an indication of fallback/retry. Wrap with e.g. `DXVK_SD865_ALLOC_TRACE=1`. Record exactly one line per failed allocation/retry, not every successful allocation. Ensure the diagnostic gets into GameNative's existing Wine log export or the user-visible DXVK logging export without ADB. Test on mocked failing allocations before WCP distribution. Do not spoof 8-bit storage, maintenance5 or memory-heap limits, and do not raise the published driver memory budget artificially.

A second trial should isolate whether the issue appears in direct Turnip versus diagnostic Wrapper/other Vulkan layers, **changing only one component at a time**.

## 2026-10-11 follow-up: raw DXVK per-module logs and 1,035,177-line Wine trace

The user supplied `ff7remake__d3d11.log`, `ff7remake__dxgi.log`, `wine_debug.log (2).txt` and an **older 2026-10-06 GameNative crash report**. No originals were committed. Source-derived findings below must not be conflated with older runs.

**Confirmed later FF7 Remake DXVK failures:** The new dedicated D3D11 log records exactly four final allocation failures (all memory types 0/1/2), then **`Exception on CS thread!`** and **`DxvkCommandList: Failed to end secondary command buffer`**. The full Wine trace agrees (allocation errors at lines 841041, 847205, 847634, 857145; command-stream exception at 951097–951098).

| New request | Alignment | Reported Vulkan heap size | DXVK allocated | Used | Reserved | Reported budget |
|---:|---:|---:|---:|---:|---:|---:|
| 22,437,888 bytes (~21.4 MiB) | 4096 | **4096 MiB** | 3988 MiB | 3765 MiB | 3775 MiB | 4702 MiB |
| 11,218,944 bytes (~10.7 MiB) | 4096 | 4096 MiB | 3988 MiB | 3739 MiB | 3775 MiB | 4656 MiB |
| 22,437,888 bytes (~21.4 MiB) | 4096 | 4096 MiB | 3988 MiB | 3739 MiB | 3775 MiB | 4696 MiB |
| 2,830,336 bytes (~2.7 MiB) | 4096 | 4096 MiB | 3992 MiB | 3765 MiB | 3779 MiB | 4571 MiB |

This new driver/wrapper reports an **exact 4-GiB heap**, compared with **7951 MiB** in the prior user capture. The reported budget *exceeds* reported heap capacity even as Vulkan allocations fail. DXVK's own tracked allocated memory is within ~104–108 MiB of that reported heap size. This makes a heap-size cap or mismatched memory accounting credible, **but not proven**: 2.7-MiB requests also fail, and no actual `VkResult` is present to distinguish driver OOM from another limit.

The DXGI companion log contains four copies of **EDID read/parse fallback** only. It has no memory errors and does not indicate the fatal cause.

**Different / older crash report:** `pluvia_crash_2026-10-06_06-51-57.txt` is from **2026-10-06**, app build `upgradeable-debug-c074383577c6`, and separately documents a **Java `UnsatisfiedLinkError`** from missing JNI implementation of `GPUImage.isHardwareBufferConfigurationSupported(short,short)` during `VulkanRenderer.onSurfaceCreated`. It is **not a stack trace from this current FF7 Remake DXVK allocator crash**; investigate separately in GameNative if it still reproduces. In that earlier trace GameNative had selected bundled `wrapper-gamenative`, Turnip v26.2.0 R4, DXVK 1.11.1 Sarek, and LSFG Native 4x, none of which proves the current DXVK 2.7.1 setup was the same.

### Diagnostic code status

On the FF7R research branch, `src/dxvk/dxvk_memory.cpp` has an **opt-in** `DXVK_SD865_ALLOC_TRACE=1` failure-only probe for *actual* first/retry VkResult, retry recovery, DXVK allocator budget guard, pooled/dedicated allocation exhaustion, selected memory type, allocation size, relevant DXVK/driver budget and usage. It retains normal retry semantics and caps probes at 128 lines per process. Source parser `tools/ff7r_alloc_trace_report.py` and tests `tests/test_ff7r_alloc_trace_report.py` were committed, as was `.github/workflows/ff7r-alloc-trace-dxvk271-wcp.yml` to build a DXVK (not Wrapper) WCP. Building on GitHub Actions **must pass before any download is presented as usable**.

Test `DXVK_SD865_ALLOC_TRACE=1` only in the *new* WCP; keep GameNative Wine debug log capture on and `DXVK_LOG_LEVEL=error` for low-noise capture. DXVK logs to its configured `DXVK_LOG_PATH` per module and also through Wine debug output. **Do not activate +vulkan tracing**. Export both GameNative Wine debug log and DXVK `d3d11.log` with the normal UI/file-manager workflow. **No ADB**.

An important follow-up beyond VkResult is reconciling `VkPhysicalDeviceMemoryProperties2.memoryHeaps[0].size` (4 GiB in newer run, 7.76 GiB earlier) against `VkPhysicalDeviceMemoryBudgetPropertiesEXT.heapBudget[0]`, across the *same driver/wrapper build*. Do not force higher `heap.size` or artificial budgets until we have the driver return code and validation.
