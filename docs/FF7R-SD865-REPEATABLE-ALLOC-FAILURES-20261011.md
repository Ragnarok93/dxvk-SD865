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
