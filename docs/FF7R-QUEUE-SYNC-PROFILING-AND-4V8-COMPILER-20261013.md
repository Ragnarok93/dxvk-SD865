# FFVII Remake SD865: queue/sync diagnostics and compiler-thread A/B — 2026-10-13

Source branch: `feature/ff7r-sd865-architecture-20261011`
Turnip branch: `Ragnarok93/Banners-Turnip:feature/sd865-a650-perf-20261012`

## Source-driven findings

From the user's third diagnostic capture after the correctly instrumented WCP was installed, DXVK emitted `DXVK-FF7R-FRAMES`, `DXVK-FF7R-PIPELINES` and `DXVK-FF7R-ONDEMAND`. Recorded presentation windows jump from approximately 6–8ms CPU-side completion intervals over long stretches to approximately 31–50ms near present IDs 6,400–6,650. This is not proof of a GPU FPS regression: game scene is not identified, input disconnect/connect events occur nearby, and prior baseline builds did not emit these timings. Keep LSFG and vkBasalt installed/on, with LSFG frame generation disabled in-game, and fix all settings per test.

Background worker compilation by the final counter: 448 worker tasks (254 GPL libraries at 2.508ms mean, 194 optimized tasks at 3.903ms mean), 14 tasks above 10ms and none above 33ms. On-demand graphics instance misses: 192 samples, mean 0.287ms, none above 10ms. These aggregate data do **not** establish that reducing worker count will help, but permit a reversible test.

## Fork survey and risk screen

Reviewed doitsujin/DXVK, Laitinlok/dxvk-gplasync-lowlatency (Vulkan 1.3 async/GPL), Digger1955/dxvk-gplall (2.7 pipeline cache/async), The412Banner/Banners-Turnip and WinNative-Emu/Drivers. Alternative GPLAsync implementations are sufficiently different from upstream and may change visual correctness or cache behavior; do not merge their render skipping or turn on new async effects without separate device testing. Turnip KGSL zero-timeout polling benefits demonstrated in VKD3D/DX12 do not automatically extend to FF7R/D3D11; existing Turnip branch already surveys/pins these fixes. Avoid A8xx-only shader changes or forcing GPU clocks. No additional shader/Turnip source optimization is justified until the next A/B.

## DXVK changes

Opt-in `DXVK_FF7R_METRICS=1` now adds structured elapsed-CPU-time aggregates:

- `DXVK-FF7R-FRAMES`: 256 intervals per window, p50/p95/p99/mean/max, `ts_us` steady clock when window ends. Interval between successful D3D11 DXGI Present completions, not GPU draw or scanout.
- `DXVK-FF7R-PIPELINES`: 64 compiled worker tasks per report, library vs optimized pipeline task averages, task backlog approximation `pending`, `ts_us`.
- `DXVK-FF7R-ONDEMAND`: 64 new graphics instance slowpath reports with `ts_us`.
- `DXVK-FF7R-ENQUEUE`: CPU queue lock/backpressure duration for command submission enqueue, including waits when queued resources exceed bounds.
- `DXVK-FF7R-QUEUE-SUBMIT`: queue worker's Vulkan command-list submission call duration including device queue mutex, measured at the CPU.
- `DXVK-FF7R-QUEUE-PRESENT`: queue worker's present call duration including Vulkan loader/layer work; this is *not* directly GPU time and includes LSFG/vkBasalt.
- `DXVK-FF7R-GPU-WAIT`: finish thread's wait for submitted command-list timeline-semaphore completion, including waiting for prior queue work and host scheduling. **Not an isolated GPU timestamp**.
- `DXVK-FF7R-CS-WAIT`: D3D11 CPU thread synchronization with command-stream worker.
- `DXVK-FF7R-FENCE-WAIT`, `DXVK-FF7R-RESOURCE-WAIT`: D3D11 waits for fences or in-use resources.

All added timings are disabled by default. No driver/Vulkan capability, shader codegen, queue fence semantics or GPU clocks changed. Window logs use `ts_us` from `std::chrono::steady_clock` across the same process. Queue/wait aggregates are cumulative with rolling log snapshots; compare counts and changes between snapshots instead of interpreting all samples as occurring precisely at the printed timestamp. The `ff7r_perf_compare.py` tool parses late/early 8-window medians and latest per-class aggregates. CPU event timestamps can help prioritize follow-up GPU timing instrumentation but are not a direct causal proof.

## Four versus eight worker experiment

DXVK's existing `dxvk.numCompilerThreads` option is supported natively; **do not add an unproven per-device worker scheduler**.

Use the same compiled WCP, Turnip build, FEX preset, visual options, save, GameNative resolution, governor, caches and LSFG/vkBasalt configuration for both settings. Avoid comparing main menu/loading windows to active battle/field windows.

**Eight-worker control**

```ini
DXVK_FF7R_METRICS=1
DXVK_LOG_LEVEL=info
DXVK_FF7R_PHASE0=1
DXVK_CONFIG=dxvk.numCompilerThreads = 8
```

**Four-worker candidate**

```ini
DXVK_FF7R_METRICS=1
DXVK_LOG_LEVEL=info
DXVK_FF7R_PHASE0=1
DXVK_CONFIG=dxvk.numCompilerThreads = 4
```

The last line above denotes an entire GameNative environment-variable value; key `DXVK_CONFIG`, value `dxvk.numCompilerThreads = 4` (or 8), not an INI file assignment to be pasted into an existing `dxvk.conf`. Confirm `DXVK: Using 4 compiler threads` or `8 compiler threads` in the log, plus the new event markers.

Perform repeated paired captures alternating eight and four workers, several minutes **in the same demanding location**, with a fixed Turnip driver, framegen OFF. Use `python3 tools/ff7r_perf_compare.py eight-workers.zip four-workers.zip`. Prefer independently collected on-screen frame statistics or Vulkan GPU timestamp queries for GPU performance claims. Guard against cache warmth, throttling and cutscene variance; match scene and ensure `DXVK_HUD=compiler` has quieted before the warm-cache steady-state pass.

**Decision path**: if four workers measurably improves late-scene p95/p99 with no major pipeline backlog, retain as an experimental profile; if backlogs/cold shader stutter worsen, revert to eight. If `GPU-WAIT` or `QUEUE-SUBMIT` counters dominate while compiler snapshots are quiet, profile Turnip queue execution/barriers rather than adding more shader-worker heuristics. If `CS-WAIT` dominates, focus DXVK command-stream scheduling. Never describe elapsed CPU queue wait as GPU execution time.

## Validation gates

- [x] Controlled source modifications and native host timing-counter tests committed.
- [ ] GitHub CI x64/x86 cross-compile success for this exact final SHA.
- [ ] GameNative WCP produced and verified contains new markers.
- [ ] At least three matched four-worker and eight-worker scene captures on SD865.
- [ ] Turnip A77/program-reference/512KiB allocator driver tests holding DXVK fixed.
