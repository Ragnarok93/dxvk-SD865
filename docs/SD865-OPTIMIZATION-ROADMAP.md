# dxvk-SD865: Snapdragon 865 / Adreno 650 Optimization Roadmap

Status: **Phase 0 — assessment and instrumentation plan**  
Base: upstream DXVK master at `852d454f6a023f04453a164e0981785fd5802cc9` (2026-10-08); `RELEASE` reports 3.1.1.  
Primary device: Samsung Galaxy S20+ (Snapdragon 865 / Adreno 650, SM8250).  
Primary environment: Android / Wine and Proton, including FEX-based x86/x64 translation, with **current Adreno 650-compatible Mesa Turnip builds (26.3.x and later when available), as well as community performance/correctness forks**. Older revisions are regression-control references, not optimization targets.

## Ground rules

1. Keep `master` an upstream-tracking branch; land independent, reversible changes via dedicated feature branches and PRs.
2. **Never bypass Vulkan feature checks**, lie about driver capabilities, or change barrier semantics without proven correctness. Driver requirements vary with driver version and cannot be inferred from GPU model alone.
3. Gate Adreno-specific behavior on actual Vulkan driver identity, GPU identity, queried features, limits and any known-good version bounds. Safe fallback is upstream behavior.
4. Prefer measurable reductions in CPU/GPU work to shader-quality reductions, risky asynchronous shader hacks, invented VRAM capacity, or arbitrary global config changes.
5. Every optimization requires an A/B toggle, repeatable benchmark, correct rendering, and rollback path. Do not regress other devices or upstream behavior.

## Hardware and compatibility facts to validate

- Qualcomm Snapdragon 865 (SM8250): eight-core Kryo 585 CPU (up to 2.84 GHz), Adreno 650 GPU, shared/unified system memory. LPDDR5 and LPDDR4X support vary by device.
- Qualcomm originally advertised Vulkan 1.1; current community Turnip 26.3 builds for Adreno 6xx advertise Vulkan 1.4.363. An advertised API version alone **does not** guarantee that all DXVK-required features/extensions are supported, or correct in a fork. Query the actual installed ICD.
- Adreno is predominantly a tiled (GMEM) GPU but can render to system memory; render-target transitions, attachment loads/stores, and unnecessary resolves can carry bandwidth/flush penalties.
- FEX may translate x86/x64 game and DXVK code; ARM64EC and native-host Vulkan paths require their own, correct toolchains. Do not assume a Windows x86 PE DLL is magically ARM-native.
- DXVK currently requests Vulkan 1.3 (`src/dxvk/dxvk_instance.h`) and requires capabilities beyond the API version. `src/dxvk/dxvk_device_info.cpp` verifies features and `src/dxvk/dxvk_limits.h` specifies 256 bytes of push data. Examples include BC texture compression, geometry shaders, dual-source blending, descriptor indexing, transform feedback, robustness and maintenance extensions.
- DXVK 3.x may fail on some Turnip/A650 driver revisions. Establish driver support before assessing frame rates. If necessary, maintain a separate compatibility baseline from a known-good older DXVK version, rather than disabling required correctness checks.

## Existing upstream code: do not duplicate

- `src/dxvk/dxvk_device.cpp::getPerfHints()`: already detects `VK_DRIVER_ID_MESA_TURNIP` and activates `preferRenderPassOps` and `preferCachedMemory`; the user already has `dxvk.tilerMode` (Auto).
- `src/dxvk/dxvk_device_info.cpp::disableUnusedFeatures()`: intentionally avoids the newer descriptor heap on Turnip and does not default to descriptor buffer there. Treat the explicit rationale as a constraint until profiling contradicts it.
- `src/dxvk/dxvk_pipemanager.cpp::startWorkers()`: scales compiler workers to reported CPU concurrency unless `dxvk.numCompilerThreads` overrides. This is a promising big.LITTLE / FEX power-and-latency experiment.
- `src/dxvk/dxvk_barrier.cpp`: barrier and attachment batching; investigate render-pass churn with captured evidence.
- `src/dxvk/dxvk_memory.cpp`: existing memory manager; tune only after tracing allocation churn/budget behavior.
- `src/dxvk/dxvk_queue.cpp`, `dxvk_presenter.cpp` and swapchains: GPU-submission timing and frame delivery instrumentation before tweaking latency.
- `.github/workflows/artifacts.yml` is **GameNative WCP only**: it compiles Win32/Win64 DLLs as intermediate inputs, packages them into one validated `.wcp`, and uploads only the WCP. The Steam Runtime native packaging, standalone DLL artifacts, merged output and Windows MSVC build workflow were removed. ARM64EC is not included.

## Phase 0 — capability audit, instrumentation, reproducible baselines (P0)

1. Add read-only Adreno 650 capability reporting: GPU/driver IDs, `driverVersion`, `apiVersion`, feature and extension presence, queue families, memory heap budget, limits, presentation support, and configuration identity. Avoid duplicate noisy logs and do not expose sensitive device data.
2. Compile x32/x64 PE DLLs internally, then **publish only one GameNative-installable `.wcp` per build**. Keep the C++/Python smoke tests without separate binary outputs. Record SHA and toolchain revisions in job logs; upstream comparisons must also be delivered as `.wcp`.
3. Define actual runtime combinations: Win32/Win64 PE and, only where supported by installed Wine/FEX, ARM64EC. A `.wcp` package is a separate launcher-specific deliverable with validated manifest/paths.
4. Prioritize DXVK 3.1.x startup with Mesa 26.3-based Turnip/Adreno 6xx builds and current optimized forks; log the **first actual incompatible capability**, rather than treating the Vulkan version as a full compatibility guarantee.
5. Capture cold/warm shader caches, 5+ runs per scene, fixed resolution and in-game settings, frametimes (median/p95/p99), 1% low FPS, GPU utilization/time if available, CPU utilization, alloc/VRAM budget, thermal state, crashes and visual hashes. Compare **DXVK upstream vs DXVK-SD865 on the same driver** before comparing driver forks.
6. Reference test workloads: Kingdom Hearts III and Crisis Core -Final Fantasy VII- Reunion (DX11), plus one D3D9 title and a generic small Vulkan/D3D11 test workload. Broaden the matrix after smoke tests.

**Phase 0 exit gate:** reliable builds and driver logs; passing startup/correctness controls; measurements capable of separating GPU, CPU, shader and presentation bottlenecks.

## Phase 1 — SD865 identity and safe profile (P0)

- Add `off / auto / on-for-testing` SD865 policy selection with **default Auto**, explicit opt-in for experiments, and logs listing each activated hint.
- Match Turnip driver ID, physical-device identification and queried capabilities. Reject unsupported combinations; fall back to upstream defaults if any predicate fails.
- Profile should not alter present mode, shader semantics, Vulkan feature advertisement, synchronization requirements or render quality.
- Add tests for SD865 detection, non-Adreno exclusion, missing optional features, driver-version boundary cases, and config override behavior.

## Phase 2 — priority CPU overhead / pipeline experiments (P1)

- Benchmark compiler worker scheduling (auto vs 2/3/4 workers) for heterogeneous Kryo cores and FEX contention. Select by warmed-playback p95/p99 frametimes as well as compilation throughput; **do not globally hardcode 4**.
- Instrument pipeline library utilization and cache hit/miss/compile time. Use GPL only with feature-complete support; preserve default fallback.
- Investigate command-list submission, descriptor-state reuse, and API marshalling overhead using trace counters, not guessed bottlenecks.
- If ARM64EC output is viable in the chosen runtime, build/test it separately; test ABI, loading, and Vulkan calls end-to-end.

## Phase 3 — tiled rendering and memory experiments (P1)

- Profile GMEM pass breaks caused by image layout transitions, depth/stencil resolves, attachment load/store and clear paths.
- Respect upstream `preferRenderPassOps` unless measured evidence supports another path. Experiment with *correct* load/store elision for provably unused attachments; check identical resulting pixels.
- Measure transfer staging sizes, mapped-resource policies, transient allocation reuse and memory-pressure stalls on UMA. Avoid interpreting total system RAM as dedicated VRAM.
- Keep shader image/layout hazard tracking fully correct; aggressive relaxed barriers remain off by default.

## Phase 4 — shader/descriptor and frame pacing experiments (P2)

- Evaluate SPIR-V generation with Mesa Turnip's actual compiler output and register-pressure / bandwidth measurements before altering shader generation or FP precision.
- Evaluate descriptor-buffer and descriptor-heap toggles as **opt-in comparisons**, since upstream explicitly avoids them on Turnip. Do not enable solely because an extension exists.
- Trace render completion, queue submit, present call and host display timing independently. A stall in Android compositor/WSI cannot necessarily be fixed within DXVK.
- Never default to async compilation that may skip rendering draws or break shader correctness.

## CI and release matrix

| Variant | Purpose | Gate |
|---|---|---|
| Upstream baseline x86/x64 PE | Reference/control | Rebuilds and smoke-tests |
| SD865 debug x86/x64 PE | Instrumentation | Unit/correctness and GPU logs |
| SD865 release x86/x64 PE | Standard deployment | Identical output, no crashes, measurable gain |
| SD865 ARM64EC PE inside WCP (future/conditional) | FEX/Wine ABI-specific optimization | Include only if compatible with GameNative content metadata and validated with the actual runtime; no standalone ABI artifact |
| GameNative WCP (sole output) | GameNative DXVK component | Root `profile.json`, x32/x64 DLLs, trusted targets, zstd/tar validation and install/uninstall tests |

Each prerelease should preserve `source SHA`, DXVK base version, build flags, architecture, file checksums, driver minimums and known limitations. Test comparisons must match driver, launcher, translator, resolution, game settings and thermal conditions.

## Success and rollback criteria

- Zero new crashes/device losses, invalid Vulkan calls, permanent hangs, missing frames or shader/texture artifacts compared with same-driver control.
- At least 5 runs across representative scenes. Retain only repeatable gains above run-to-run noise; review mean and median FPS, p95/p99 frametime, 1% low, cold compile times and memory.
- A change improving peak FPS while worsening long frametime spikes or breaking other drivers fails acceptance.
- Every behavior must be reversible by config and kept isolated in reviewable changes.

## First implementation PRs (after roadmap review)

1. **P0-A: DXVK Adreno 650 capability report and device/driver profile predicate** (no optimizations enabled).
2. **P0-B: baseline CI, smoke-test suite, runtime capability test matrix and artifact identification**.
3. **P1-A: shader compilation worker scheduling benchmark/toggle** (first measurable experiment).
4. **P1-B: GMEM/renderpass event counters and renderpass correctness tests**.
5. **P1-C: memory allocation/staging counters and opt-in tweaks**.

## Sources

- Qualcomm Snapdragon 865 technical specs: https://www.qualcomm.com/smartphones/products/8-series/snapdragon-865-5g-mobile-platform
- Mesa Freedreno / Turnip architecture: https://docs.mesa3d.org/drivers/freedreno.html
- DXVK driver support: https://github.com/doitsujin/dxvk/wiki/Driver-support
- FEX/ARM64EC integration guidance: https://wiki.fex-emu.com/index.php/Development:ARM64EC


## Update: modern Turnip / optimized-fork baseline (2026-10-09)

### Updated target assumption

The target is **the newest Turnip driver that actually supports Adreno 650**, including Mesa-main-based Android packaging and optimized third-party builds. Do not optimize for the minimum supported 2020 Qualcomm Vulkan version or target only Mesa 24.x/25.x. Compatibility with old Turnip is a secondary regression control, never permission to weaken feature checks.

Verified public driver families relevant to the A650 as of this update:

| Candidate | Source / timestamp | Relevance and restrictions |
|---|---|---|
| StevenMXZ 26.3.0-R6 | 2026-09-30, Vulkan 1.4.363 | **Primary packaged Android/AdrenoTools baseline**: advertised specifically for A6xx/A7xx; device must still be checked |
| The412Banner 26.3.0-20261005 | 2026-10-05, Mesa main commit `84673c2`, Vulkan 1.4.363 | **Fresh CI comparison** for A6xx/A7xx; maintainer says CI-built, **not device-tested** |
| whitebelyash Stable Turnip V2 | 2026-09-19, Mesa 26.2 | Community fork regression/correctness comparison; reportedly supports upstream A6xx set |
| NetherSX2Turnip / Tranquility6789 26.2.0-R5P SD865 patched | 2026-06-04 | **A650 crash-control candidate**, but Winlator/GameNative fixes are not guaranteed |
| Weab-chan/K11MCH1 25.x/26.0 releases | historical | Useful for older driver behavior and GMEM/SYSMEM/autotuner comparisons, **not** primary version ceiling |
| Newer 26.3-main Adreno 650 builds | when available | Evaluate by exact Mesa SHA, fork patches, binary fingerprint and Vulkan reports; never assume date/version implies better FPS |

The StevenMXZ **Gen8 V37** driver targets A8xx; it must **not** be confused with the co-released **26.3.0-R6 for A6xx/A7xx**. Likewise, a packaged Linux-container Turnip build cannot automatically be dropped into an AdrenoTools Android ICD location.

### Critical Adreno 650-specific correctness finding

NetherSX2-Turnip maintainer `nckstwrt` documented an Adreno 650 crash workaround in June 2026: the underlying fix patches `tu_create_image` so UBWC is **not enabled on images with `VK_IMAGE_USAGE_TRANSFER_SRC_BIT`** (potential readback images). Globally disabling UBWC via `TU_DEBUG=noubwc` can avoid some crashes but harms performance. This driver workaround was reported to help Eden, but user testing documented unresolved Winlator/GameNative crashes/reboots on some titles.

Consequences for DXVK-SD865:
- Include **readback / transfer-source image workflows, UBWC failures, GPU device loss and SoC reboot** as explicit correctness tests.
- Make no unconditional global `noubwc` override. DXVK does not own Turnip's per-image UBWC decision; prefer a supported/fixed driver and report exact compatibility.
- Audit DXVK image creation and readback usage only to identify actual transfer-source patterns. Do not strip legitimate Vulkan usage flags merely to work around the issue.
- If a driver-side workaround is necessary, evaluate a **reproducible source-level Turnip patch**, independently of DXVK optimization. Do not advertise binary-patched emulator drivers as broadly reliable for Wine without validation.
- Capture the exact driver source revision, patch set, driver binary fingerprint and app path (Eden vs GameNative/Winlator) for reproducible testing.

### Optimization targets adjusted for Mesa 26.3+

1. **CPU-side DXVK/FEX overhead:** pipeline worker concurrency, state transition churn, descriptor updates and command submission. Use GPU vs CPU profiling to prioritize.
2. **Tile and bandwidth efficiency:** use Mesa's GMEM/SYSMEM autotuner and instrument DXVK's render-pass boundaries, load/store/resolve decisions, and layout transitions. Avoid global forced GMEM or SYSMEM as a default; compare autotuner policies only where offered and validated by the chosen fork.
3. **Shader compiler compatibility and efficiency:** investigate actual IR3 shader results, subgroup and shaderFloat16 capabilities; do not reduce shader correctness or precision by default.
4. **Memory and readback correctness:** allocation churn, memory budget, UBWC interaction, staging and fence waits.
5. **Pipeline and descriptor paths:** do not auto-enable descriptors merely because current Turnip advertises the extension; upstream avoids descriptor buffers/heaps on Turnip for performance/driver reasons. Use optional A/B toggles if features are complete.
6. **Frame-time stability:** separately track CPU frame preparation, Vulkan submit, GPU completion, presentation and compositor queueing so WSI/Android stalls are not misattributed to DXVK.

**Driver selection protocol:** record `vendorID`, `deviceID`, `driverID`, `driverVersion`, `apiVersion`, complete relevant `VkPhysicalDeviceFeatures2` and extension set, limit/budget data and hashed driver binary; separate the selected fork/patch lineage from advertised device names (which can be spoofed). Select safely based on queried capabilities and A650 identity, never solely by an untrusted version string.

**Performance acceptance:** for each driver combination first hold the driver fixed and compare upstream DXVK vs optimized DXVK. Only then compare Turnip standard vs patched with *the same DXVK* to isolate benefits. Retain safety/correctness and p95/p99 frametime as release gates. No claims of measured gains until on-device evidence exists.

References:
- https://github.com/StevenMXZ/Adreno-Tools-Drivers/releases
- https://github.com/The412Banner/Banners-Turnip/releases
- https://github.com/whitebelyash/AdrenoToolsDrivers/releases
- https://github.com/nckstwrt/NetherSX2-Turnip/issues/70
- https://github.com/Tranquility6789/Turnip-A650-Patched-Drivers/releases
- https://docs.mesa3d.org/drivers/freedreno.html
