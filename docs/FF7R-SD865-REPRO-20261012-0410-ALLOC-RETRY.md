# FFVII Remake S20+ — October 12 04:10 UTC allocation/retry capture

**Subsystem owner: DXVK-SD865.** User uploaded 155-line `ff7remake__d3d11.log`, 4-line `ff7remake__dxgi.log`, 1,263-line Wine trace, separate GameNative app log and an **older Oct 6 JNI crash log**. All original logs stay with user conversation, not in Git. Native Turnip KGSL/Android memory-pressure interpretation is kept in [the Turnip report](https://github.com/Ragnarok93/Banners-Turnip/blob/research/ff7r-a650-kgsl-oom-20261012/docs/investigations/FF7R-A650-REPRO-20261012-0410-MEMORY-PRESSURE.md).

## What DXVK alone demonstrates

- `DXVK-SD865-POOL state=init enabled=0` appears twice. The existing diagnostic pool WCP is installed but **ordinary 256 MiB device / 64 MiB mapped policy** was deliberately selected for a control test. `heap0_size_bytes=8337227776` = 7,951 MiB without GameNative 2-GiB Vulkan-heap override.
- DXVK reports **117** `stage=driver_retry` events: **116** with `first_vkresult=-2, retry_vkresult=-2, recovered=0` and **one with `first_vkresult=-2, retry_vkresult=0, recovered=1`**. The one recovery occurs on a 256 MiB memory-type-0 allocation with `first_attempt_id=30`, `retry_attempt_id=31`, DXVK allocated 3,829,399,552 bytes (~3,652 MiB) before success. Driver returning success after the first failure is evidence the existing empty-chunk free/retry occasionally works.
- **Eight** `stage=pool_exhausted` records, **four** `DxvkMemoryAllocator: Memory allocation failed` blocks, then terminal `Exception on CS thread!` and `DxvkCommandList: Failed to end secondary command buffer` (D3D11 log lines 154–155).
- Final per-event DXVK `dxvk_allocated_bytes=4,202,692,608` = **4,008 MiB** and `dxvk_used_bytes=3,928,373,504` ~3,746 MiB. Final formatted error heap row: `0: 7951 4008 3746 3706 4370` (MiB Size, Allocated, Used, driver Reserved, Budget). The driver budget is only an estimate, not proof successful `vkAllocateMemory` is possible.
- All rejected DXVK calls use `VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT` (`flags=2`), pooled `dedicated=0`, and include Vulkan memory types 0,1,2. These were also present in previous runs; neither the BDA flag nor a fixed 4-GiB GPU address limit has been shown to be the direct cause.
- `ff7remake__dxgi.log`: 4 EDID/colorimetry fallback messages only. The error-only DXVK log cannot verify whether the manually entered `DXVK_CONFIG=dxgi.maxDeviceMemory = 3072` was parsed or effective, and **cannot** be interpreted as an actual 3072-MiB allocation quota.

## Correlation with native source, not a DXVK source bug

The Wine log **also** contains 128 native diagnostic KGSL `GPUMEM_ALLOC_ID errno=12` records, and four opt-in `FF7R-A650-KGSL-PRESSURE` snapshots of very low physical MemAvailable (303–414 MiB) and rapidly growing guest-host process swap. The Vulkan failures are **real downstream driver rejections**, not DXVK's discretionary heap budget guard. See Turnip report for exact figures and kernel limitations. DXVK's policy to attempt free+retry is demonstrably useful for the single recovered 256 MiB request but cannot solve sustained system memory pressure on its own.

## Next DXVK work, only if supporting evidence warrants

- Preserve normal and experimental pool WCPs as separate A/B controls. The 64/32 MiB mode previously reclaimed 47 wholly empty chunks (1,452 MiB *cumulatively*) but still failed near the same memory level. Don't keep reducing 8-MiB chunks, and don't claim this fixed the crash.
- Verify effective game-visible DXGI memory via **INFO-level `Effective configuration`** or a bounded DXGI effective config marker. `dxgi.maxDeviceMemory` is **reported video memory**, not a Vulkan hard allocation cap.
- Quantify live D3D11 buffer / texture / staging allocations and UE4 streaming behavior at matched scenes; avoid logging every call, and only change resource strategy if profiling shows meaningful avoidable peaks.
- Do not spoof Vulkan heaps, advertise unsupported features, drop required BDA flags, or turn the UMA budget estimator into a hard quota that would only fail the game earlier.

**Conclusion:** Real native driver OOM at ~4GiB tracked allocations, with 1 successful retry followed by 116 unrecovered paired retries. Diagnosis belongs below DXVK in Turnip/Android memory management; adjust DXVK only where it can reduce genuine live resource demand.
