# dxvk-SD865: Snapdragon 865 / Adreno 650 Optimization Roadmap

Status: **Phase 0 — assessment and instrumentation plan**  
Base: upstream DXVK master at `852d454f6a023f04453a164e0981785fd5802cc9` (2026-10-08); `RELEASE` reports 3.1.1.  
Primary device: Samsung Galaxy S20+ (Snapdragon 865 / Adreno 650, SM8250).  
Primary environment: Android / Wine and Proton, including FEX-based x86/x64 translation, with Mesa Turnip Vulkan drivers.

## Ground rules

1. Keep `master` an upstream-tracking branch; land independent, reversible changes via dedicated feature branches and PRs.
2. **Never bypass Vulkan feature checks**, lie about driver capabilities, or change barrier semantics without proven correctness. Driver requirements vary with driver version and cannot be inferred from GPU model alone.
3. Gate Adreno-specific behavior on actual Vulkan driver identity, GPU identity, queried features, limits and any known-good version bounds. Safe fallback is upstream behavior.
4. Prefer measurable reductions in CPU/GPU work to shader-quality reductions, risky asynchronous shader hacks, invented VRAM capacity, or arbitrary global config changes.
5. Every optimization requires an A/B toggle, repeatable benchmark, correct rendering, and rollback path. Do not regress other devices or upstream behavior.

## Hardware and compatibility facts to validate

- Qualcomm Snapdragon 865 (SM8250): eight-core Kryo 585 CPU (up to 2.84 GHz), Adreno 650 GPU, shared/unified system memory. LPDDR5 and LPDDR4X support vary by device.
- Qualcomm originally advertised Vulkan 1.1; modern Mesa Turnip implements newer Vulkan on Adreno 6xx, but *each installed ICD/build* must be queried.
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
- `.github/workflows/artifacts.yml`: upstream mingw-w64 (x86/x64 PE) and Steam Runtime native outputs; no SD865-specific ARM64EC/Android package validation yet.

## Phase 0 — capability audit, instrumentation, reproducible baselines (P0)

1. Add read-only Adreno 650 capability reporting: GPU/driver IDs, `driverVersion`, `apiVersion`, feature and extension presence, queue families, memory heap budget, limits, presentation support, and configuration identity. Avoid duplicate noisy logs and do not expose sensitive device data.
2. Establish a host build and unit smoke-test CI on both 32- and 64-bit PE outputs, retaining upstream comparison artifacts. Record source SHA and toolchain revisions.
3. Define actual runtime combinations: Win32/Win64 PE and, only where supported by installed Wine/FEX, ARM64EC. A `.wcp` package is a separate launcher-specific deliverable with validated manifest/paths.
4. Verify DXVK 3.1.x startup with installed Turnip versions; log the **first actual incompatible capability**, rather than falsely assuming all modern drivers support the required set.
5. Capture cold/warm shader caches, 5+ runs per scene, fixed resolution and in-game settings, frametimes (median/p95/p99), 1% low FPS, GPU utilization/time if available, CPU utilization, alloc/VRAM budget, thermal state, crashes and visual hashes.
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
| SD865 ARM64EC PE (conditional) | FEX/Wine ABI-specific optimization | Correct loader, imports and Vulkan interop |
| Launcher package (conditional) | GameNative/GameHub integration | Exact packaging spec, install/uninstall validation |

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
