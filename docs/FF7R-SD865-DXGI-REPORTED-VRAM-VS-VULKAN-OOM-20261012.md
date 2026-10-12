# FFVII Remake — Why DXVK reported VRAM does not cap Turnip memory allocations

Date: 2026-10-12 UTC. **Subsystem owner:** DXVK. GameNative setting propagation is documented in `Ragnarok93/GameNative`; Mr Purple T30/Turnip KGSL findings should go into the user's separate Turnip fork once its repository URL is confirmed. No source code patch is included in this report.

## Verified DXVK source paths

1. `src/dxgi/dxgi_options.cpp` reads `dxgi.maxDeviceMemory` with `config.getOption<int32_t>("dxgi.maxDeviceMemory", 0)` and converts MB to bytes (`<< 20`).
2. `src/dxgi/dxgi_adapter.cpp:480-482` applies this value only to the `deviceMemory` value in a DXGI adapter description **if lower than available memory**; it is not passed into Vulkan's `vkAllocateMemory` or a DXVK heap guard.
3. `src/util/config/config.cpp:1400-1445` parses config lines only if they begin with a valid key and `=`. `Config::getUserConfig` at ~1652–1692 reads an optional `dxvk.conf` file, then `DXVK_CONFIG` by splitting on `;`. A GameNative-generated **quoted, multi-line `DXVK_CONFIG`** can fail to parse entirely. That serialization is a **GameNative bug candidate** and should be fixed/tested there, not in DXVK's standard parser. User-entered `DXVK_CONFIG` can override it in GameNative's environment merge; the screenshots truncate the value and do not conclusively prove whether it was recognized.
4. `src/dxvk/dxvk_memory.cpp:686` sets **`heap.enforceBudget = !m_device->isUnifiedMemoryArchitecture() ...`**; Adreno 650 is UMA, so the allocator's discrete-GPU budget guard does not physically enforce a 3072-MiB cap. `src/dxvk/dxvk_memory.cpp:1339` enforces its internal budget only if `type.heap->enforceBudget`. Thus DXVK allocating ~4 GiB is expected to be *possible* even when a smaller `VK_EXT_memory_budget` or DXGI-advertised memory value is configured. Neither reports an actual available fixed GPU VRAM partition on this shared-memory SOC.
5. GameNative Graphics Max Device Memory → `WRAPPER_VMEM_MAX_SIZE=2048` is **separate**: the pinned wrapper changes `VkMemoryHeap.size`, which DXVK uses to initialize internal heap budgets. In the A650 UMA path a 2GiB advertised heap still does not prevent DXVK allocating nearly 4GiB. Removing that override restored 7,951-MiB heap reporting but did not prevent native Vulkan OOM.

## On-device observations (independent captures)

The source of numeric measurements is user-exported GameNative Wine and `ff7remake__d3d11.log` diagnostic traces; see pre-existing run-specific files:

- Baseline `docs/FF7R-SD865-DEVICE-OOM-ZERO-OVERRIDE-20261011.md`: 94 paired driver-retry events, all `first_vkresult=-2`, `retry_vkresult=-2`, `recovered=0`; DXVK allocation ~4,004 MiB at failure, driver budget ~4,530 MiB, Vulkan heap 7,951 MiB. Vulkan `VkResult=-2` is a real driver allocation rejection.
- Pool-experiment `docs/FF7R-SD865-POOL-EXPERIMENT-DEVICE-RESULT-20261012.md`: `DXVK-SD865-POOL state=init enabled=1`; 47 fully empty chunks and 1,452 MiB **cumulatively** freed. Yet allocation failed near 4,002 MiB. Diagnostic opt-in changes buffer pool max chunks from 256/64 MiB to 64/32 MiB; it is **not a fix**.
- Deliberate pool-off A/B `docs/FF7R-SD865-UI-CONFIG-AND-POOL-OFF-CONTROL-20261012.md`: `enabled=0`; 111 failed paired Vulkan retries and ~4,008 MiB allocated. The user confirmed screenshots were taken before switching the flag to 0; no confirmed env-propagation defect here.
- All failing `stage=driver_retry` calls are mapped buffer pool allocations in memory types 0/1/2, with `VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT` present (`flags=2`). They return Vulkan OOM even for 4–16 MiB requests. The log does **not** prove a hard 4 GiB GPU VA ceiling or a BDA implementation defect; allocation failure may be physical or virtual memory pressure or native KGSL ioctl policy.

## Practical diagnosis / proposed instrumentation

- **Confirmed:** Changing `dxgi.maxDeviceMemory` changes **reported DXGI dedicated VRAM**, not Turnip's actual allocation permission. Reducing DXGI VRAM might indirectly change FFVII Remake's texture-streaming decisions, but only if effective config is parsed and the engine honors that value.
- **Needed to verify this specific test:** one short `DXVK_LOG_LEVEL=info` capture showing `Found config env:` and `Effective configuration:`, plus desired 3072-MiB value and proper parsing; alternatively a compile-time diagnostic in DXVK's DXGI adapter reporting the **actual applied** adapter description. Do not infer it merely from a manual UI field.
- **Prohibited false fix:** Do not overwrite real Vulkan budgets, spoof `VkMemoryHeap.size`, disable buffer device address requirements, or assume 4 GiB device allocations can be removed by logging no more than 3072 MB in DXGI.
- **Next allocator investigation:** profile live pooled-buffer demand, mapped memory and actual `vkAllocateMemory` errors; native Turnip needs its **KGSL ioctl errno** because `VK_ERROR_OUT_OF_DEVICE_MEMORY` is too generic.

Cross-repository references:
- [GameNative settings / quote parser report](https://github.com/Ragnarok93/GameNative/blob/research/ff7r-vram-config-20261012/docs/investigations/FF7R-SD865-VRAM-CONFIG-PROPAGATION-20261012.md)
- [FEX 2610 bounded evidence report](https://github.com/Ragnarok93/FEX/blob/research/ff7r-memory-triage-20261012/docs/investigations/FF7R-SD865-FEX2610-NONCAUSAL-TRIAGE-20261012.md)

**Conclusions are from DXVK and GameNative source and user logs, not proof of a specific private Mr Purple T30 KGSL implementation.**

## Turnip repository routing confirmed (2026-10-12)

User identified the designated Turnip fork as [`Ragnarok93/Banners-Turnip`](https://github.com/Ragnarok93/Banners-Turnip). The driver-specific investigation is now committed at [`docs/investigations/FF7R-SD865-KGSL-VULKAN-OOM-20261012.md`](https://github.com/Ragnarok93/Banners-Turnip/blob/research/ff7r-a650-kgsl-oom-20261012/docs/investigations/FF7R-SD865-KGSL-VULKAN-OOM-20261012.md), commit `a1f89412d024`.

**Provenance qualification:** Banners-Turnip's Standard A6xx driver is built from pinned/upstream Mesa, whereas the user's currently tested driver is Mr Purple T30 / PurpleVK; source/binary equivalence has **not** been confirmed. Turnip build, KGSL ioctl failures, driver errno and GPU virtual-memory questions belong to the linked driver report, not this subsystem's patch queue.

## 2026-10-12 direct driver confirmation (cross-repository reference)

The newly uploaded FF7R DXVK D3D11 diagnostic log contains **117** `DXVK-SD865-ALLOC stage=driver_retry` records, all with `first_vkresult=-2 retry_vkresult=-2 recovered=0`, **eight** pool-exhaustion records and **four** terminal allocation errors. The user also exported a Wine log containing **native Turnip/KGSL diagnostic tags**. Those show `IOCTL_KGSL_GPUMEM_ALLOC_ID` returning **`errno=12 (ENOMEM)`**, with Turnip then returning Vulkan `-2`. **KGSL cause and new native-pressure instrumentation are owned and recorded in [Banners-Turnip](https://github.com/Ragnarok93/Banners-Turnip/blob/research/ff7r-a650-kgsl-oom-20261012/docs/investigations/FF7R-A650-DEVICE-KGSL-ENOMEM-20261012.md), not here.**

This definitively confirms that the recorded DXVK failures are not produced by an internal DXVK or user-set DXGI memory budget guard. It does not establish a hard 4-GiB GPU-address cap. In this run `DXVK_SD865_POOL_EXPERIMENT=0` and the driver-facing heap is the original **7951 MiB**; the intentionally toggled flag matches the control-run plan. The per-call Vulkan buffer-device-address flag is **not equivalent to KGSL FORCE_32BIT**: the native trace shows `force_32bit=0` and `replayable=0` for the failures.

**Next DXVK work:** To influence memory *usage* rather than merely reported VRAM, measure FFVII Remake's live resource pressure and confirm whether `dxgi.maxDeviceMemory` was correctly parsed and honored by Unreal Engine. The failing native KGSL allocation path is not fixable by only printing a smaller DXGI memory number.
