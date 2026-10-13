# FFVII Remake A650: opt-in compilation/present diagnostic pass — 2026-10-13

Branch: `feature/ff7r-sd865-architecture-20261011`. Target: S20+ Snapdragon 865 / Adreno 650, GameNative D3D11 with Vulkan 1.3. Preserve LSFG/vkBasalt in container (LSFG FG OFF in game), low textures and the existing Vulkan feature gates.

## Motivation

Comparison of user-provided Current.zip vs DXVK.2.7.1.gplasync_Mr.Purple.T30.zip showed successful initialization/GPL in both runs, but no real-frame timing or pipeline compile latencies. Sequence counts and driver memory-budget snapshots cannot show FPS. Both archives produce `benchmark_valid: false` with this parser because neither contains the opt-in markers; no speedup is claimed.

## Source changes

- `DXVK_FF7R_METRICS=1` enables bounded DXGI Present-completion cadence collection, D3D11 only. Each 256 intervals, emit `DXVK-FF7R-FRAMES` mean, p50, p95, p99 and max (microseconds). Rejected pauses above 3 seconds reset the current window. Disabled builds incur only an env/static check, with no sampling clock reads or allocations. This measures CPU-side Present completion cadence, **not GPU execution timestamps or actual scanout**.
- In DXVK's shader-worker pool, the same flag enables accumulated background pipeline-library and optimized-pipeline CPU compilation times, reporting `DXVK-FF7R-PIPELINES` once on first task and then once per 64 tasks. Includes counts above 10ms/33ms. Does **not** measure synchronous graphics pipeline creation, GPU cost or cache hit rates. Disabled path skips clock reads/atomics.
- Added portable native percentile test, Python parser tests and ZIP/directory comparison script. Keep low-noise DXVK_LOG_LEVEL=info when capturing diagnostics.

## How to run

GameNative environment: `DXVK_FF7R_METRICS=1` and `DXVK_LOG_LEVEL=info`. Preserve `DXVK_FF7R_PHASE0=1` if already enabled. Collect `ff7remake__dxgi.log`, `ff7remake__d3d11.log` and optionally Wine/Android logs into a ZIP per trial.

Run `python3 tools/ff7r_perf_compare.py baseline.zip candidate.zip` after at least 768 real frames per capture (3 x 256 interval windows). Compare multiple matched captures in the same FF7R save location with same resolution, driver, DXVK, FEX, caches and thermal settings. A minimum of three windows is not a statistical significance guarantee. The script reports **median of each 256-frame window's p95**, not a global pooled p95. Do not compare differing-duration present counters or LSFG-generated frames as FPS.

## Experimental matrix

1. Current DXVK + SD865 Cortex-A77 Turnip control versus same DXVK + program-reference (isolates program-state pointer).
2. Current DXVK + program-reference versus same DXVK + pipeline-512k (isolates A650 backing allocator).
3. For DXVK-specific trials, keep the Turnip driver fixed. External GPLAsync baseline lacks these custom markers, so source-independent GameNative frametime capture must be used to compare that version.

Retain each Turnip candidate only if present-cadence and visual/memory behavior do not regress across repeated runs; pursue expensive synchronous on-demand pipeline compilation if compilation timing strongly correlates with spikes. Previous compiled-build results do not establish device FPS benefit.

## Validation

- Host g++ C++17 percentile sampler test passes, including p95/p99 tails and >3s pause reset.
- Python archive parser tests pass, and parsing both October 13 historical captures correctly yields no instrumentation data and no speedup assertion.
- Windows x64/x86/CI GameNative WCP validation is a separate gate; do not mark this complete without run success and device testing.
