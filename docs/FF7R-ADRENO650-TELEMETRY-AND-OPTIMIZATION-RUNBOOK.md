# FFVII Remake / Adreno 650 telemetry and optimization runbook

Status: instrumentation and measurement contract for the Vulkan 1.3-compatible DXVK 2.7.1-derived build. This document does not claim a performance gain until matched device captures demonstrate one.

## Dedicated opt-in telemetry switch

Use **`DXVK_FF7R_METRICS=1`** to enable FFVII Remake frame/present and synchronization timing counters compiled into this fork. This is separate from `DXVK_LOG_LEVEL`: the latter controls log severity, while `DXVK_FF7R_METRICS` enables the custom sampling code.

Recommended GameNative environment for a diagnostic capture:

```sh
DXVK_FF7R_METRICS=1
DXVK_FF7R_ONDEMAND=1
DXVK_LOG_LEVEL=info
DXVK_LOG_PATH=/path/to/writable/ff7r-logs
```

- `DXVK_FF7R_METRICS=1`: opt-in frame/present cadence and GPU/resource wait timing counters.
- `DXVK_FF7R_ONDEMAND=1`: opt-in render-thread pipeline cache-miss slow-path timing. Background worker compilation-duration summaries are gated by `DXVK_FF7R_METRICS=1` in the current implementation.
- `DXVK_FF7R_PIPELINE_LOOKUP_CACHE`: the experimental per-pipeline last-hit cache is **enabled by default**; set it to `0` to disable it for matched A/B runs. It only shortcuts lookup of an existing immutable state instance; it does not change pipeline creation, handles, or Vulkan synchronization.
- `DXVK_FF7R_COMPILER_THREADS`: for `ff7remake_.exe`, optionally set `2`, `4`, `6`, or `8` to compare compiler worker counts. If `dxvk.numCompilerThreads` is explicitly configured, the FF7R environment override takes precedence when valid.
- `DXVK_LOG_LEVEL=info`: retain the informational telemetry lines without enabling debug/trace noise.
- `DXVK_LOG_PATH`: directory for per-DLL logs. Use a location writable by the GameNative/Wine runtime. The resulting files are named from the game executable and DLL, for example `ff7remake__dxgi.log` and `ff7remake__d3d11.log` (exact executable basename may vary).
  
If the runtime cannot set more than one environment variable at a time, set them individually in GameNative's environment-variable UI. The values must be present in the game process, not only in a shell that is not its parent.

## Expected telemetry markers

| Marker | Meaning | Important limitation |
|---|---|---|
| `DXVK-FF7R-TELEMETRY` | Startup confirmation of `metrics`, `on_demand`, `lookup_cache`, and selected Vulkan device | Confirms the environment reached device initialization; it does not prove the candidate improves performance |
| `DXVK-FF7R-FRAMES` | CPU-side Present-completion interval statistics: mean, p50, p95, p99, max | Not GPU execution time or physical display scanout |
| `DXVK-FF7R-PIPELINES` | Background pipeline-library / optimized-pipeline compilation CPU durations | Does not include all synchronous pipeline creation or GPU execution |
| `DXVK-FF7R-ONDEMAND` | Render-thread cache-miss slow-path timing, including relevant lock wait / instance creation | Only samples the instrumented slow path |
| `DXVK-FF7R-LOOKUP` | Sampled CPU time, entries scanned, and cache-hit percentage for graphics-pipeline lookup | Samples one lookup per 256 calls; diagnostic-only and not representative of GPU time |
| `DXVK-FF7R-FENCE-WAIT` | CPU time spent waiting for a fence | A wait duration is evidence of a stall, not proof of its root cause |
| `DXVK-FF7R-RESOURCE-WAIT` | CPU time waiting for a resource to become reusable | Does not imply the wait can safely be removed |

Not every marker is emitted by every capture. Frame/present cadence needs real frames; on-demand pipeline timing requires cache-miss slow paths; lookup timing samples one call in every 256 and requires enough lookups; synchronization markers require the relevant waits to occur. A missing marker alone is not proof that the feature is broken. Check the exact binary build, variable propagation, log path permissions, and workload coverage first.

## Compiler-worker A/B experiment

Use this only after collecting a baseline log with the same scene and cache conditions. The current worker telemetry reports aggregate pending tasks and mean compilation duration for pipeline libraries and optimized pipelines; it does **not** yet report per-priority queue wait time or render-thread stalls attributable to compilation. Do not infer queue contention from worker count or aggregate compile duration alone.

1. Keep `DXVK_FF7R_METRICS=1` and `DXVK_FF7R_ONDEMAND=1` fixed for diagnostic trials. Change only `DXVK_FF7R_COMPILER_THREADS`.
2. Compare `2`, `4`, `6`, and `8` workers, with the same GameNative/Wine runtime, Turnip revision, resolution, scene, route, cache state, and trial duration.
3. Capture at least three matched trials per worker count; alternate order where practical to reduce thermal/order bias. Record temperatures and any throttling.
4. Compare native-present frame-time median/p95/p99 and first-use hitching, not just mean pipeline compilation time or CPU utilization. Treat `DXVK-FF7R-PIPELINES` as compilation CPU-time evidence, not GPU time.
5. Keep the current diagnostic default at four workers unless matched device captures show a repeatable alternative with no worse tail latency, shader-compilation hitching, stability, or thermals.

No worker-count setting is presumed optimal. If the experiment points to queue contention, add targeted queue-wait/backlog instrumentation as a separate change before redesigning worker scheduling.

## Capture protocol

1. Record the exact DXVK commit, DLL hashes, GameNative build, FEX/runtime version, Turnip driver revision, game build, resolution, graphics settings, save/location, and environment variables.
2. Keep unrelated settings fixed. In particular, do not change allocator/pool configuration, compiler worker count, Turnip build, resolution, or frame generation between the baseline and candidate runs.
3. Capture cold-cache and warm-cache trials separately. Use the same repeatable gameplay route and input sequence.
4. Capture at least 768 real presented frames per trial where possible (three 256-interval windows). Do not count generated/interpolated frames as native game presents.
5. Perform at least three matched trials per variant. Log ambient/device thermal state and discard runs with materially different throttling or background activity.
6. Save the complete per-DLL logs and external GameNative/Android frame-time capture together in a uniquely named archive. Never overwrite the baseline.
7. Compare captures with `python3 tools/ff7r_perf_compare.py baseline.zip candidate.zip`. The script's windowed statistics are not a guarantee of statistical significance; inspect raw windows and external frame-time traces too.
8. For the lookup-cache A/B test, enable `DXVK_FF7R_METRICS=1` in both diagnostic runs and toggle only `DXVK_FF7R_PIPELINE_LOOKUP_CACHE` between unset (enabled) and `0` (disabled). The comparison script reports sampled lookup mean-nanosecond, entries-scanned, and cache-hit-percentage deltas when both archives contain `DXVK-FF7R-LOOKUP` markers. Then repeat performance mode with metrics disabled; do not use the diagnostic timings as the final performance verdict.

## Low-overhead and performance captures

Run two modes:

- **Diagnostic mode:** `DXVK_FF7R_METRICS=1`, `DXVK_FF7R_ONDEMAND=1`, `DXVK_LOG_LEVEL=info`. Use this to attribute stalls and verify functionality.
- **Performance mode:** disable custom timing variables and use the same external frame-time capture method for both builds. Use this to judge whether the candidate actually improves throughput or frame pacing.

This distinction matters because instrumentation itself can perturb CPU scheduling and log I/O. The existing timing counters use bounded/sparse reporting, but a diagnostic capture is still not the authoritative FPS result.

## Acceptance gates for optimization patches

- Build: x86 and x64/WCP artifacts build from the recorded commit; preserve Vulkan 1.3 compatibility.
- Functionality: expected marker appears when its trigger occurs; no device loss, crash, persistent artifact, or invalid resource lifetime.
- Performance: compare median FPS/frametime and p95/p99 frametime over matched repeated runs, plus thermal state and memory behavior.
- Retention: keep a patch only when the measured target metric improves repeatably without unacceptable regressions. Do not infer a speedup from fewer log lines, a higher pipeline count, a memory-budget snapshot, or a single peak-FPS reading.
- Rollback: retain a clean baseline artifact and keep experimental changes isolated so each can be reverted independently.

## Immediate optimization order

1. Complete the source-level 2.7.1-to-3.1.1 backport ledger and reject any patch requiring Vulkan 1.4 unless a valid Vulkan 1.3 implementation exists.
2. Use frame and pipeline telemetry to classify the dominant limit: CPU submission, pipeline compilation, resource/fence waits, GPU-bound work, or thermal throttling.
3. Change one measured bottleneck at a time. Prioritize synchronization/render-pass work only where the trace supports it; then evaluate state/descriptor overhead, staging/allocation behavior, and a separately gated Sarek-style asynchronous pipeline-variant compilation experiment.
4. Re-run correctness, memory-pressure, cold/warm cache, and sustained thermal tests before accepting any optimization.

## Current limitations

The present/pipeline/wait markers are CPU-side instrumentation and cannot independently provide GPU timestamps or true scanout timing. External GameNative frame-time capture is required for a reliable frame-pacing comparison. A successful compile is not a device validation result; no performance gain should be claimed until the same Adreno 650 device has completed matched baseline/candidate runs.
