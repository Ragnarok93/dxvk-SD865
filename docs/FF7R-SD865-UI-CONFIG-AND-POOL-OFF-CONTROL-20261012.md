# FFVII Remake on Galaxy S20+ — pool-off control and UI config audit (2026-10-12)

## Evidence
User submitted six GameNative setting screenshots, `ff7remake__d3d11.log` (147 lines), `ff7remake__dxgi.log` (4 lines), `wine_debug.log (2).txt` (780 lines), and a historical 2026-10-06 Android app crash. The historical crash (`GPUImage.isHardwareBufferConfigurationSupported` missing JNI method) is not the Vulkan allocation failure under investigation.

## Observable mismatch: screenshot vs actually running DXVK

GameNative UI **shows** environment `DXVK_SD865_POOL_EXPERIMENT=1`. In the uploaded **same-batch DXVK/Wine logs**, the allocator initializes **twice** with:

```text
DXVK-SD865-POOL state=init enabled=0 device_pool_cap_bytes=268435456 mapped_pool_cap_bytes=67108864 empty_chunk_policy=dxvk_default initial_heap0_size_bytes=8337227776
DXVK-SD865-ALLOC state=diagnostic_wcp_loaded capture_enabled=1 ...
```

And all allocation failures have `pool_experiment=0`, `empty_chunks_reclaimed=0` and `empty_bytes_reclaimed=0`. Therefore the log was recorded with **the ordinary 256/64-MiB policy**. Screenshots could have been taken after settings changes; do **not** assume environment injection is broken until run/screenshot chronology is clarified, saved, and restarted. Earlier independent log in `FF7R-SD865-POOL-EXPERIMENT-DEVICE-RESULT-20261012.md` proved `enabled=1` worked and reclaimed 47 chunks.

## Measured crash

- 111 `stage=driver_retry` events, each with first and retry `VK_ERROR_OUT_OF_DEVICE_MEMORY`, `recovered=0`.
- 8 pool exhaustion lines (= four failed allocations, each reporting device-local and fallback property flags), plus four terminal `DxvkMemoryAllocator: Memory allocation failed` blocks; request sizes 2,830,336 bytes twice and 5,660,672 bytes twice.
- memory type 0: 63 failed events; type 1: 24; type 2: 24; rejected backing request sizes from 256 MiB down to 4 MiB. These are failure-events, **not 111 separate resource requests**.
- First failed backing chunk: 256 MiB, `dxvk_allocated_bytes=4,097,835,008` (**3,908 MiB**); `dxvk_used_bytes=3,853,980,672` (~3,675 MiB).
- Last failed backing chunk: 8 MiB at `dxvk_allocated_bytes=4,202,692,608` (**4,008 MiB**), `dxvk_used_bytes=3,967,952,128` (~3,784 MiB), Vulkan driver memory budget ~4,733 MiB. The 4-MiB failure appears earlier in the same terminal sequence.
- DXGI log only lists failed EDID/colorimetry metadata parsing, no resource allocation failure.
- Wine log duplicates DXVK failures and shows X11 disconnection at teardown. No evidence here that X11 caused the primary resource-allocation failure.

This third run again shows roughly **4 GiB DXVK allocated** and Turnip rejecting tiny backing chunks. Do not claim a proven 4-GiB hardware limit: external Android memory pressure and internal driver allocation constraints remain possible.

## UI configuration observations

- Adrenotools Turnip on; memory resource type auto; BCn emulation auto with compute decode; LSFG-VK off; DRI3 on. No automatic BCn-native compressed-memory inference should be made without a driver/wrapper capability audit.
- Top-level graphics `Present Modes=mailbox`; renderer present FIFO; env `MESA_VK_WSI_PRESENT_MODE=mailbox`: potential mismatch, choose consistent FIFO and remove env override for low-memory test, keeping others fixed.
- FEXCore 2610 FF7R Phase0/FF7R Balanced active. Box64 compatibility preset is not the active x64 emulator for FFVII Remake.
- Wine `Video Memory Size=2048 MB` and GPU string spoof `NVIDIA GeForce GTX 480` do not physically limit Vulkan allocations.
- Screenshot shows `DXVK_CONFIG` field starts with `dxgi.m...`, but **field is visually truncated**, so full config string cannot be confirmed. DXVK_LOG_LEVEL=error suppresses DXVK's INFO `Found config env` and `Effective configuration` output. To verify, use `DXVK_LOG_LEVEL=info` for one short run and look for `dxgi.maxDeviceMemory = 3072` (or another exact intended MB value), then revert.
- Upstream DXVK source `src/dxgi/dxgi_options.cpp` treats `dxgi.maxDeviceMemory` as reported memory (megabytes converted to bytes), **not a Vulkan vkAllocateMemory hard cap**. `src/util/config/config.cpp` parses `DXVK_CONFIG` split by semicolons and logs `Found config env` at INFO.
- FEX DISKCACHE values in the image have clipped text fields; do not infer exact numeric values from cropped UI.

## Next gates

1. Save edits explicitly in GameNative; fully restart the game/container; confirm next `DXVK-SD865-POOL state=init enabled=<expected>` marker before interpreting allocations. The previous opt-in run already established it can enable successfully.
2. Check DXGI config with `DXVK_LOG_LEVEL=info` and proper exact field value; game-facing VRAM reporting may affect UE4 texture streaming, but it is not a hard cap.
3. With matched save/resolution/driver/FEX, test actual texture/streaming demand (Low textures, conservative UE4 pool) and measure peak allocations. Consider wrapper BCn expanded-texture memory.
4. Investigate Turnip/Adreno GPU memory allocation and BDA failure path; **do not spoof Vulkan heap or disable required Vulkan features**.
