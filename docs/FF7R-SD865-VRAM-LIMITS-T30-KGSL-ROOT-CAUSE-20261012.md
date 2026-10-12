# FFVII Remake / Snapdragon 865 — Why VRAM limits do not constrain Turnip allocations (2026-10-12)

**Scope.** Investigated the actual `Ragnarok93/GameNative` launcher source, `Ragnarok93/dxvk-SD865` 2.7.1 fork, `leegao/mesa-wrapper-CI` `gn_wrapper2` source, a public current Mesa Turnip source mirror (`DsoTsin/mesa-manet`), published MrPurple T30 release metadata, and the user's latest x64 D3D11/Wine allocation logs. The published MrPurple `purple-turnip` repository contains the T30 binary release but **does not contain its precise Mesa source/patch tree**, so paths identified in Mesa are ***hypotheses for the actual T30 binary*** until an actual binary or source match is validated. Do not confuse wrapper reports with a fingerprint of the native driver.

## 1. Confirmed behavior from phone logs

- `DXVK-SD865-POOL state=init enabled=0` in latest log is the **intentional control run** (the screenshot showing `DXVK_SD865_POOL_EXPERIMENT=1` predates the user's explicit change to 0). **NOT a GameNative env propagation defect.**
- Latest D3D11 log: **111 driver_retry events**, all with `first_vkresult=-2, retry_vkresult=-2, recovered=0`; 8 `pool_exhausted` reports; four final `DxvkMemoryAllocator: Memory allocation failed` blocks. Failures in Vulkan memory types 0,1,2 including a 4-MiB backing-allocation request. Normal DXVK tracked heap allocation approached **4008 MiB** with **7951 MiB Vulkan heap size** and driver-reported budget around **4733 MiB**; real driver or lower-level allocation refused. `flags=2` = Vulkan `VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT`, but this is not proof that BDA caused the failure.
- Prior pool-enabled experiment (`enabled=1`) reclaimed **47 completely empty chunks / 1452 MiB cumulatively**, yet driver OOM still appeared around **4002 MiB** of DXVK allocation. So fully empty chunk retention is not the primary unaddressed bottleneck.
- Prior `Graphics Max Device Memory=2048` deliberately forced the Vulkan heap size to 2048 MiB while DXVK still allocated ~3968 MiB. Later setting 0 restored reported Vulkan heap to 7951 MiB and did not eliminate OOM.

## 2. Three different non-enforcing VRAM settings

**A. Wine Video Memory Size: 2048 MB.** `Ragnarok93/GameNative/app/src/main/java/app/gamenative/ui/component/dialog/WineTab.kt` stores `videoMemorySize` as a Wine container choice. It is not a Vulkan `vkAllocateMemory` quota and no measured Turnip allocation count is gated by this value. The screenshot shows 2048, which did not stop allocation >4 GiB.

**B. Vulkan wrapper Graphics Max Device Memory: 0/2048/etc.** `GraphicsTab.kt` persists `maxDeviceMemory`; `XServerScreen.kt:6108-6110` sets `WRAPPER_VMEM_MAX_SIZE` for positive values only. Wrapper `src/vulkan/wrapper/wrapper_physical_device.c:930-959` rewrites `VkPhysicalDeviceMemoryProperties.memoryHeaps[0].size` and the Properties2 equivalent only. It does not clamp Turnip or KGSL allocations and is not automatically reconciled with `VkPhysicalDeviceMemoryBudgetPropertiesEXT.heapBudget`, so `heapBudget > heapSize` can be reported. Keep 0 for unspoofed heap info.

**C. DXVK `dxgi.maxDeviceMemory = 3072`:** `src/dxgi/dxgi_options.cpp` parses this from DXVK config, and `src/dxgi/dxgi_adapter.cpp:480-482` caps only the adapter's `DedicatedVideoMemory`. Crucially **`DxgiAdapter::QueryVideoMemoryInfo` (`dxgi_adapter.cpp:264-299`) separately sums the driver-derived Vulkan `memoryBudget` without the option**. A game may therefore observe 3 GiB via adapter description while querying a 4.5+ GiB runtime budget; which FF7R uses is not yet traced. **Neither API is a physical allocation quota.**

## 3. Confirmed GameNative automatic DXVK_CONFIG formatting bug

`Ragnarok93/GameNative/app/src/main/java/com/winlator/core/DXVKHelper.java:20-64` constructs:
```text
"dxgi.maxDeviceMemory = 2048\ndxgi.maxSharedMemory = 2048\n"
```
(i.e. a leading quote, embedded literal newline separators, trailing quote), then calls `envVars.put("DXVK_CONFIG", content)`. DXVK-SD865 `src/util/config/config.cpp:1400-1439, 1649-1690` calls `parseUserConfigLine` on **semicolon-separated** environment fragments, accepting only valid key chars at the start; the initial double quote means the whole fragment is not recognized as a key. Even just removing the quotes is insufficient for multiple entries because `DXVK_CONFIG` is split by semicolons, *not newline characters*. **Thus automatically generated config values are invalid and can be silently ignored.**

**Important scope:** This does not establish that the user's manually entered value failed. GameNative `XServerScreen.kt:2519` calls `DXVKHelper.setEnvVars` during extraction, then **later** `XServerScreen.kt:4143` calls `envVars.putAll(container.envVars)`; therefore the manual `DXVK_CONFIG` field has final precedence and, when the exact value is `dxgi.maxDeviceMemory = 3072`, it can be parsed correctly. However the screenshot truncates it and `DXVK_LOG_LEVEL=error` suppresses `Found config env` / effective config informational markers. Check a single `DXVK_LOG_LEVEL=info` capture before declaring the 3072 setting applied.

**Suggested safe GameNative patch** (NOT applied yet; needs unit/integration tests): use `StringBuilder` or a list to construct the environment DXVK_CONFIG as `dxgi.maxDeviceMemory = 2048; dxgi.maxSharedMemory = 2048` with **no outer quotes** and preserve internal quotes in values such as `dxgi.customDeviceDesc = "NVIDIA ..."`. Keep existing per-container overrides last, add a test for exact runtime value after env merging, and only set DXVK_CONFIG if nonempty. A directly generated `DXVK_CONFIG_FILE` could alternatively point to a correctly written `dxvk.conf` with newline-separated entries. The helper currently sets that file path but does not itself write it.

## 4. Why reported Vulkan budget is larger than allocatable memory

The *public Mesa Turnip source mirror* `src/freedreno/vulkan/tu_device.cc` calculates `heap.size` via `os_get_gpu_heap_size`, optionally capped by reported `va_size`, and `VkPhysicalDeviceMemoryBudgetPropertiesEXT.heapBudget` via `tu_get_budget_memory`. That calls Mesa's `vk_physical_device_heap_budget_from_system(0.9f, heap_size, heap_used)`. In `src/vulkan/runtime/vk_physical_device.h` this is `0.9 * os_get_available_system_memory + heap_used`, clamped to heap size. It is **an estimate based on system-wide free RAM and tracked allocations**, not a per-process KGSL GPU-IOVA, BO, fd, cgroup/Android resource limit or guaranteed successful `vkAllocateMemory`.

The same public Turnip `tu_AllocateMemory` passes most ordinary allocations to `_tu_init_memory`/KGSL; `src/freedreno/vulkan/tu_knl_kgsl.cc:300-338` invokes `IOCTL_KGSL_GPUMEM_ALLOC_ID` and maps **any failure** to `vk_errorf(..., VK_ERROR_OUT_OF_DEVICE_MEMORY, "GPUMEM_ALLOC_ID failed (%s)", strerror(errno))`. Without driver-side stderr/`errno` telemetry, we **cannot** distinguish `ENOMEM`, `ENOSPC`, `EACCES`, IOVA exhaustion, driver/kernel bookkeeping or other failures solely from DXVK's `VkResult=-2`. Android other processes and external imported allocations may affect available memory.

**32-bit boundary nuance:** Turnip's `TU_BO_ALLOC_NO_32B_ROLLOVER` sets `KGSL_MEMFLAGS_FORCE_32BIT` for certain indirect command buffers on applicable firmware, as documented in `tu_device.h:~735` and `tu_knl_kgsl.cc:~320`. However `tu_AllocateMemory` reacts to `VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_CAPTURE_REPLAY_BIT`, not the normal `DEVICE_ADDRESS_BIT=2`; ordinary DXVK buffer-device-address allocations do **not** automatically imply `TU_BO_ALLOC_NO_32B_ROLLOVER`. Therefore don't claim `flags=2` proves the first-4-GiB GPU-VA restriction. A repeatable ~4GiB total is suspicious but needs KGSL address-availability and errno evidence.

## 5. Wrapper allocation path: conditional, and likely bypassed for this Wine setup

Wrapper `gn_wrapper2/src/vulkan/wrapper/wrapper_device_memory.c:318-405` has host-visible placed-memory emulation using **auto DMA-BUF → AHardwareBuffer → opaque fd**, but it activates **only when** `VK_EXT_map_memory_placed` and its `memoryMapPlaced` feature are enabled on the logical device. The earlier user's full Wine trace `wine_debug.log (5).txt` explicitly reported twice: `Skipping extension 'VK_EXT_map_memory_placed', no implementation found in winevulkan.` For a similar current Wine build, this would make wrapper `vkAllocateMemory` fall back to the driver's dispatch method rather than using these resource backends. **But the latest error-level logs don't enumerate enabled extensions**, so direct driver attribution still needs verification. The wrapper is in the path and we should not assume it is the root cause without raw/wrapper allocation-stage markers.

BCn wrapper default AUTO mode checks the driverID: in this public wrapper source `WRAPPER_EMULATE_BCN>=3` maps to `0` when the base driver reports Mesa Turnip. Thus the user's `BCn Auto / Compute` selection does **not** by itself prove wrapper-side ASTC expansion or extra BCn emulation overhead; require actual device markers.

## 6. Mr Purple T30 release provenance

The public `MrPurple666/purple-turnip` GitHub release `vturnip_mrpurple_T30-toasted.adpkg` labels it Mesa `26.3.0-devel`, Vulkan `1.4.359`, unified A6xx/A7xx/A8xx; it is supplied as a `.adpkg.zip` binary artifact. The public repository's actual tracked tree only contains `README.md`; **exact T30 source patches and native ioctl return diagnostics are not available there**, and the user's deployed binary hash/embedded build revision has not been validated. The Mesa path above is **upstream-source-derived**, not proof of the custom T30 patch implementation.

## 7. Prioritized next technical steps without ADB

1. **Fix GameNative's automatic DXVK_CONFIG serialization**, add tests for both generated limits and user overrides; do not assume this will prevent Vulkan OOM.
2. **Verify actual DXVK config with one `DXVK_LOG_LEVEL=info` capture**, capture `Found config env` and `Effective configuration`, and return to error logging. Leave GameNative Graphics Max Device Memory at 0. Confirm game receives adapter desc and, if possible, the separate DXGI `QueryVideoMemoryInfo` value with bounded read-only instrumentation.
3. **Instrument allocation-layer provenance** in the actual deployed PurpleVK and/or native Turnip test driver: per failed `vkAllocateMemory` print whether wrapper placed-memory emulation or direct dispatch was used, raw `VkResult`, memory type/flags/size; inside Turnip `tu_knl_kgsl.cc`, gate `GPUMEM_ALLOC_ID` failure-only diagnostics to `errno`, requested size, KGSL flags (especially `FORCE_32BIT`), reported BO IOVA and driver per-process tracked BO bytes. Avoid per-frame logging and preserve Vulkan features. Ensure logs are exportable via GameNative UI without ADB.
4. A controlled A/B should compare same scene and Vulkan driver/wrapper with a **genuinely lower live resource budget** (e.g. Low textures and game-supported Unreal streaming pool limits) against unchanged DXVK/Turnip, not merely smaller *reported* DXGI VRAM. A strict DXVK allocator hard cap would just return OOM earlier unless the game responds by freeing/reusing resources.
5. If OOM remains near 4 GiB of actual BOs with 4-MiB kernel allocations failing, analyze kernel-side KGSL GPU VA span, BO usage, cgroup/Android memory pressure and imported memory residency. Distinguish native vs wrapper before changing driver GPU-VA policy; do not disable BDA or remove firmware workarounds without tests.

### Source paths
- GameNative: `app/src/main/java/com/winlator/core/DXVKHelper.java`; `app/src/main/java/app/gamenative/ui/screen/xserver/XServerScreen.kt`; `GraphicsTab.kt`, `WineTab.kt`.
- DXVK fork: `src/util/config/config.cpp`; `src/dxgi/dxgi_options.cpp`, `src/dxgi/dxgi_adapter.cpp`; `src/dxvk/dxvk_memory.cpp`.
- Wrapper mirror `leegao/mesa-wrapper-CI` ref `gn_wrapper2`: `src/vulkan/wrapper/wrapper_device_memory.c`; `wrapper_physical_device.c`.
- Public Mesa mirror `DsoTsin/mesa-manet`: `src/freedreno/vulkan/tu_device.cc`, `tu_device.h`, `tu_knl_kgsl.cc`; `src/vulkan/runtime/vk_physical_device.h`.
- MrPurple T30 release: `https://github.com/MrPurple666/purple-turnip/releases/tag/vturnip_mrpurple_T30-toasted.adpkg`.
