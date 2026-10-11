# FFVII Remake — second allocation trace confirms driver OOM, 2026-10-11

## Evidence and scope

User-uploaded files on 2026-10-11 22:49 UTC: `ff7remake__d3d11.log` (25 lines, 7877 bytes), `ff7remake__dxgi.log` (4 lines), `wine_debug.log (2).txt` (661 lines), and `pluvia_crash_2026-10-06_06-51-57 (1).txt` (older Android crash). Original logs are **not** checked into Git. This is a **second device run**, distinct from the 15:06 UTC 9-failure run in `docs/FF7R-SD865-DEVICE-OOM-CONFIRMED-20261011.md`.

## Device evidence

| Measurement | Prior diagnostic run | New diagnostic run |
|---|---:|---:|
| `stage=driver_retry` records | 9 | **18** |
| First and retried `VkResult` | all `-2` | all `-2` |
| Recovered after retry | 0 | 0 |
| Minimum rejected chunk | 32 MiB | **16 MiB** |
| Failed game allocation | 22,369,792 bytes (21.33 MiB) | **11,185,024 bytes (10.67 MiB)** |
| Final DXVK heap allocated | 4004 MiB | **3988 MiB** |
| Final DXVK heap used | 3781 MiB | **3775 MiB** |
| Final DXVK heap reserved | 3785 MiB | **3783 MiB** |
| Advertised physical heap size | 7951 MiB | **7951 MiB** |
| Driver-reported budget | 4798 MiB | **4634 MiB** |

All 18 records show:
- `first_vkresult=-2`, `retry_vkresult=-2`, `recovered=0` -> **real `VK_ERROR_OUT_OF_DEVICE_MEMORY` from the Vulkan driver**, not just a DXVK-side guard.
- `heap=0`, `dedicated=0`, `flags=2` (`VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT`) and `buffer_usage=137727` -> pooled, buffer-device-address allocations. This **does not prove** BDA support itself is defective: BDA is common to all observed rejected calls but also potentially to successful earlier allocations.
- `memory_type=0` on 17 events, `memory_type=1` on one event; these types map to one heap.
- Rejected chunks: **3×256 MiB**, **3×128 MiB**, **8×64 MiB**, **2×32 MiB**, **2×16 MiB**. These are logged across the life of the game, NOT necessarily an uninterrupted single fallback sequence. Current DXVK source uses variable chunk sizes and retries in `allocateChunkInPool`.
- The final `stage=pool_exhausted` lists `requested_memory_types_mask=7` but `eligible_memory_types_mask=3`, `property_flags=6` = `HOST_VISIBLE | HOST_COHERENT`, `no_allocation_mode=0`. The final allocation could only use types 0/1 given the requested properties and DXVK selection rules.
- The first failure was seen already at **3908 MiB** allocated by DXVK; late failures reached 3988 MiB. Final DXVK allocated-but-not-used headroom is **213 MiB**. The driver budget at failure is **646 MiB higher than DXVK allocated**; a reported `VK_EXT_memory_budget` number is not a guarantee that a new allocation succeeds under Android shared memory / IOVA/BO constraints.
- DXVK records one terminal `Memory allocation failed` error. The Wine log later reports a critical-section wait timeout and disconnect of X11; these are associated with hang/teardown, but there is no usable specific FEX/driver/native game stack proving a precise downstream instruction fault.
- DXGI log: only EDID/colorimetry parse fallback; not a credible direct cause of Vulkan OOM.

**Critical limits:** There is no opt-in startup signature (`state=diagnostic_wcp_loaded`), `first_attempt_id`, `heap_size_bytes` nor settings dump in the uploaded log, so this run appears to use the earlier diagnostic WCP. The files **do not establish** that `dxgi.maxDeviceMemory = 3072` was present, recognized, or effective; avoid claiming either success or failure for the recommended DXGI VRAM-advertisement experiment. Nor does a 7951-MiB reported heap and ~3988 MiB of DXVK allocations establish a hard 4-GiB hardware limit.

The October 6 `pluvia_crash` file is an unrelated historical `GPUImage.isHardwareBufferConfigurationSupported(short,short)` Java JNI `UnsatisfiedLinkError`, not a new FFVII Remake driver event.

## Code review and next tests

[DXVK fork `src/dxvk/dxvk_memory.cpp`](https://github.com/Ragnarok93/dxvk-SD865/blob/feature/ff7r-sd865-architecture-20261011/src/dxvk/dxvk_memory.cpp): `allocateMemory` uses host-visible mapped pool when `HOST_VISIBLE` is requested; `allocateChunkInPool` retries smaller pool chunks, and `allocateDeviceMemory` itself frees empty chunks and retries Vulkan once. Normal fixed resource buffer usage and BDA flag semantics **must** remain intact. [DXVK memory header](https://github.com/Ragnarok93/dxvk-SD865/blob/feature/ff7r-sd865-architecture-20261011/src/dxvk/dxvk_memory.h) sets 256-MiB absolute pool max, 4-MiB min; `determineMaxChunkSize` limits mappable pool max (host-visible 64-MiB on 64-bit in stock logic), but observed 256-MiB Vulkan attempts may correspond to **other resource requests** or a different allocation pathway. Do not assume every diagnostic event is a step in the final 10.67-MiB resource allocation.

**Prioritized next controlled sequence (no ADB):**

1. **Confirm configuration applied before interpreting it:** run a diagnostic with DXVK `info` on briefly, or add an explicit read-only emitted `maxDeviceMemory` configuration marker in a new WCP; avoid millions of Wine `+vulkan` trace lines. Capture the actual allocated/current budget and source settings.
2. A/B *same* Turnip T30, Wrapper/PurpleVK, FEX, resolution and DXVK, with vs. without `dxgi.maxDeviceMemory=3072`. This changes VRAM **reported to the game**, not allocator memory permission.
3. If still failing, make an **experimental build-only option** to lower DXVK's **mapped/global buffer pool chunk growth** and eagerly reclaim whole empty chunks, with strict correctness tests, enabled by a unique WCP version. Keep all BDA requirements unchanged. Measure allocated-vs-used slack and failure threshold against unchanged original diagnostic WCP. Do not present this as a proven fix.
4. If driver OOM persists at similar live memory, consider direct Turnip vs wrapper isolation, native driver allocator/ION/IOVA pressure audit, and sampling of Android memory pressure without modifying device memory heap properties.
5. Do not spoof 8-bit storage, BDA support, heap size, maintenance5, or claim the reported budget can be allocated in one call.

The older and current devices logs prove real Vulkan driver OOM, not merely DXVK's self-imposed budget guard. More diagnostics must focus on **how to reduce live/pooled GPU BO demand**, not inflate the reported GPU memory budget.

## 2026-10-11 configuration clarification: 3072-MiB test was not applied as intended

The user clarified: “I set it as an environment variable.” In **DXVK-SD865 source**, `src/dxgi/dxgi_options.cpp` obtains `dxgi.maxDeviceMemory` using `config.getOption<int32_t>("dxgi.maxDeviceMemory", 0)`, and `src/util/config/config.cpp` reads configuration options through the **`DXVK_CONFIG`** environment variable or a `dxvk.conf` file selected by `DXVK_CONFIG_FILE`. There is **no automatic standalone `dxgi.maxDeviceMemory` environment-variable lookup**. Thus, if the user set a variable with that exact name, it would be ignored. If they used `DXVK_CONFIG` with the key/value inside it, it *would* be parsed; confirm exact variable name before declaring the experiment invalid.

**GameNative no-ADB setup for actual retest:**

```ini
DXVK_CONFIG=dxgi.maxDeviceMemory = 3072
```

In GameNative's two-field environment-variable editor: **Name** = `DXVK_CONFIG`, **Value** = `dxgi.maxDeviceMemory = 3072`. If `DXVK_CONFIG` already has a value, append `; dxgi.maxDeviceMemory = 3072`; do not overwrite any other options. Alternative file-based configuration: put `dxgi.maxDeviceMemory = 3072` into `dxvk.conf` and ensure its path is known to DXVK. This affects *reported DXGI video memory*, **not the real Vulkan allocation budget or driver memory cap**, and FFVII Remake may or may not alter texture/streaming behavior accordingly.

**Experimental-status correction:** The two 2026-10-11 allocator logs confirm driver OOM, but by themselves do **not** demonstrate that 3072 MiB reporting changed streaming behavior, because the exact environment-variable name has not been recorded. Do not claim that experiment failed until configured through one of the verified input mechanisms.
