# FFVII Remake — first S20+ 64/32-MiB DXVK pool experiment results (2026-10-12 UTC)

## Input and provenance
The user uploaded the live-phone `ff7remake__d3d11.log` (116 lines, 48,447 decoded characters), `ff7remake__dxgi.log` (4 lines), `wine_debug.log (1).txt` (6,569 lines), and an **old** `pluvia_crash_2026-10-06_06-51-57 (1).txt`. All raw uploaded logs remain private and were not committed. This report records independently counted values from the source log, not generated or simulated runtime metrics. The uploaded October 6 GameNative JNI linkage crash is unrelated to this October 12 FFVII Remake Vulkan OOM run.

## Policy actually activated

The D3D11 module log begins with *two* memory allocator initialization markers:

```text
DXVK-SD865-POOL state=init enabled=1 device_pool_cap_bytes=67108864 mapped_pool_cap_bytes=33554432 empty_chunk_policy=reclaim_all_wholly_empty initial_heap0_size_bytes=8337227776
DXVK-SD865-ALLOC state=diagnostic_wcp_loaded capture_enabled=1 heap_count=1 heap0_size_bytes=8337227776 ...
```

Therefore this is a **valid enabled experiment**, not a stale WCP or missing env variable. Device pool capped to 64 MiB, mapped pool capped to 32 MiB, fully empty chunks eligible for immediate reclamation, initial Vulkan heap 7,951 MiB (no 2-GiB override). The Wine log independently repeats these markers at ~2365, 2396, 3085–3086.

## Measured failure counts and memory levels

- **80 `stage=driver_retry` events** in D3D11 and mirrored in Wine; all return **`first_vkresult=-2`, `retry_vkresult=-2`, `recovered=0`** = Turnip `VK_ERROR_OUT_OF_DEVICE_MEMORY` on both attempts. Vulkan allocation attempt IDs start at 124/125 and end at 288/289, showing successful attempts/interleaving that aren't logged. Failed requests are `dedicated=0`, `flags=2` (BDA), `buffer_usage=137727` and `heap=0`.
- **Memory types:** 0: 40 rejected paired attempts; 1: 20; 2: 20. Count includes one logged event for each first+retry pair, **not 80 logical game resource requests**.
- **Failed chunk sizes:** 64 MiB: 16 events; 32 MiB: 23; 16 MiB: 22; 8 MiB: 13; and ~21.33 MiB: 6 events. (The 21.33-MiB size comes from a specific requirement path; do not assume every event is a pooled chunk from the caps.)
- **8 `stage=pool_exhausted`** records, corresponding to four sets of both property-flags=1 (device-local) and property-flags=0 (fallback); the unsatisfied logical resource sizes are 11,218,944 bytes (~10.70 MiB), 22,437,888 bytes (~21.40 MiB), and twice 5,660,672 bytes (~5.40 MiB).
- **4 `DxvkMemoryAllocator: Memory allocation failed` errors** at the end of the D3D11 log and also mirrored in Wine; no usable native driver stack. X-server connections disconnect at Wine lines 6566–6569 (teardown, not an independent demonstrated root cause).
- **First rejected Vulkan allocation:** DXVK `dxvk_allocated_bytes=4,117,168,128` = **3,926.44 MiB**, actively used ~3,710.12 MiB; failed pool chunk 64 MiB. This is about 18 MiB later than the prior standard-pool first rejection (~3,908 MiB), but the captures are not guaranteed matched game progression.
- **Final rejected Vulkan allocation:** DXVK `dxvk_allocated_bytes=4,196,859,904` = **4,002.44 MiB**, actively used `3,940,905,984` = **3,758.34 MiB**, difference **~244.1 MiB allocated but not marked actively used**. The final error's formatted heap summary prints allocated `4002`, used `3755`, reserved `3773`, budget `4626` MiB; instantaneous per-event stats differ slightly from the later formatted summary as allocation state changes.
- **Driver-reported budget at final failure:** `driver_budget_bytes=4,850,712,576` = **4,626 MiB** (not a promise of allocatable contiguous GPU memory); tracked driver allocated `driver_allocated_bytes=3,956,328,960` = ~3,773 MiB. Vulkan heap size `8,337,227,776` = 7,951 MiB.
- **Reclamation:** First and every subsequent error record shows **`empty_chunks_reclaimed=47` and `empty_bytes_reclaimed=1,522,532,352` = 1,452 MiB**. This is a lifetime cumulative amount reclaimed **before the first logged driver-retry event** and it did not change during the recorded terminal OOM sequence. It is **not 1,452 MiB of currently free GPU memory**. When the allocator could no longer allocate a fresh 8-MiB chunk, no additional empty DXVK chunks were available for that error recovery path according to the counters.
- The DXGI companion log contains **only EDID/colorimetry fallback messages**, no allocator failure signature.

## Baseline comparison and conclusion

The preceding **normal 256/64-MiB allocator run** (documented in `FF7R-SD865-DEVICE-OOM-ZERO-OVERRIDE-20261011.md`) reported Vulkan heap 7,951 MiB, final DXVK allocated **4,004 MiB**, **94** driver-retry logs, eight pool-exhaustion events, and an effective minimum rejected chunk of 16 MiB. This experimental run gets as low as **8 MiB** and reclaims **47 completely empty chunks / 1,452 MiB cumulatively**, but still fails at **4,002 MiB** allocated. Do not infer success or regression from event counts or game resource sizes because run durations, game state, and concurrent Android memory demand are not identical.

**Confirmed:** (1) the experiment reached the game and changed pool policy; (2) empty-chunk reclaim happened; (3) real Turnip Vulkan driver OOM persists on buffer-device-address allocations with both retry calls rejected. **Not proven:** hard 4-GiB GPU-address limit; BDA-specific driver bug; physical vs contiguous VRAM exhaustion; game-facing `DXVK_CONFIG=dxgi.maxDeviceMemory = 3072` actually parsed; lower GPU live-memory need is achievable by pool policy alone.

**Engineering direction:** This experiment is a valuable negative result: reclaiming whole empty chunks **alone** does not fix the immediate OOM. Stop blindly lowering chunk sizes (8 MiB already rejected) or spoofing Vulkan heap/feature/budget numbers. Prioritize (a) verifying game-facing DXGI VRAM cap with explicit effective-config marker; (b) reducing **live** game resource/streaming memory demand (textures, UE4 pool, streaming options) and measuring peak; (c) native Turnip/Mesa/Android memory and buffer-device-address allocation limits, ideally with driver-side diagnostic codes; (d) considering partial-chunk occupancy/defragmentation only with correctness proof, since ~244 MiB DXVK allocated-but-not-used is not automatically wholly reclaimable.

Keep the successful original diagnostic WCP as rollback. Experimental WCP must remain opt-in and not merge as default without runtime evidence of benefit.
