# Using the DXVK-SD865 foundation build

Scope: current Mesa Turnip / Adreno 650 (Snapdragon 865), including community forks that report `VK_DRIVER_ID_MESA_TURNIP`.

**Phase-0 state:** detection, targeted capability logs and optional worker scheduling are implemented. No shader or resource-binding semantics are changed. No frame-rate gain has yet been measured.

## New `dxvk.conf` options

```ini
# Auto=detect, False=disabled, True=force on Qualcomm Turnip (diagnostic only).
dxvk.sd865Profile = Auto

# Log detected driver and selected core/extension capabilities (only Qualcomm Turnip).
dxvk.sd865Diagnostics = True

# Opt-in experiment: 0=unchanged upstream scheduling, 1..8=worker count.
dxvk.sd865CompilerThreads = 0
```

To A/B test shader compilation scheduling, try `dxvk.sd865CompilerThreads = 2`, `3` and `4` on **the same Turnip driver, game, resolution, temperature and FEX setup**. Restart the application for each run. Restore to `0` for the untouched scheduler behavior. An explicit `dxvk.numCompilerThreads` override **always wins** and disables the SD865-specific worker override.

`dxvk.sd865Profile = False` disables detection/tuning but still allows passive driver logging when diagnostics are enabled. The explicit value `True` can force the experimental profile if a Qualcomm Turnip fork changes the Adreno 650 device name; it will *not* activate on another Vulkan vendor or a proprietary Qualcomm driver. Do not force this mode on an A660/A730; the diagnostic line warns if hardware identification was not verified. Only turn on optional worker tuning on a verified Adreno 650.

## What the logs show

Upon successful device creation, expected lines begin `DXVK-SD865:`:

- Vulkan driver ID (must be Mesa Turnip), reported GPU name, vendor/device IDs, decoded driver version, Vulkan API version.
- Whether Adreno 650 was confidently identified, whether the profile is active, and whether it was forced.
- **Enabled** features: dynamic rendering, sync2, descriptor buffer/heap, graphics pipeline libraries, float16, maintenance5/6 and memory-budget support.
- Maximum push constants, minimum subgroup size and DXVK's unified-memory check.
- When worker override is set, the effective compiler thread count.

Upstream DXVK already emits full selected queue families, memory heap sizes/budgets and enabled extensions at startup. Do not interpret an enabled-feature log as a complete listing of every feature *supported* by the driver; for complete probing use `vulkaninfo` / the launcher Vulkan capability exporter from the same driver binary.

If device initialization fails before DXVK creates a logical device, the log may contain only the original DXVK compatibility failure. Record that error and the Vulkan capability dump before changing Vulkan requirements.

## Reproducible driver matrix

For each driver package, record the ZIP/source URL, Mesa commit/patch set, SHA-256 digest, `driverID`, Vulkan API version, GPU vendor/device IDs, Wine/FEX build, and Vulkan loader selected by the launcher. An optimized fork may spoof its displayed version, so do not infer capabilities from the version string.

Use this comparison matrix:

| Driver | DXVK | Worker mode | Purpose |
| --- | --- | --- | --- |
| Identical current Turnip | Original upstream 3.1.1 | Upstream default | Control |
| Identical current Turnip | DXVK-SD865 | `0` | Detect unintended baseline regressions |
| Identical current Turnip | DXVK-SD865 | `2`, `3`, `4` | Isolate worker scheduling |
| Alternative A650 Turnip fork | Both binaries | Same mode | Isolate *driver* differences |

Capture cold and warm compilation separately; median FPS, 1% low, 95th/99th-percentile frametimes, crashes, missing objects, temperature and compile activity. Five repeatable runs per sample are recommended. Do not enable unsafe async shader skips, relaxed UAV barriers or descriptor-model overrides in the baseline.

## Build and tests

- `.github/workflows/sd865-policy.yml` compiles `tests/sd865_policy.cpp` with C++17 and tests driver identity, opt-in/forced profile behavior, and worker-count precedence/limits.
- The customized `.github/workflows/artifacts.yml` compiles Windows x32/x64 PE DLLs **internally**, packages them into **one GameNative-installable `.wcp`**, validates the compressed archive/required DLLs, and uploads **only that `.wcp` build payload**. Linux-native and MSVC artifacts are no longer produced. GitHub wraps the downloadable WCP artifact in a ZIP; extract the inner `.wcp`. ARM64EC binaries are not yet built; on-device A650/Turnip runtime testing remains mandatory. See [GameNative testing](./SD865-GAMENATIVE-TESTING.md).
- Test compile/run locally if desired: `g++ -std=c++17 -Wall -Wextra -Werror -pedantic tests/sd865_policy.cpp -o /tmp/sd865-policy-tests && /tmp/sd865-policy-tests`.

The `dxvk.sd865CompilerThreads` experiment is intentionally opt-in until measurements justify an automatic policy.

## Profiling render passes and shader compilation (opt-in)

The Phase-1 instrumentation has **two independent switches**. Both are disabled in normal use.

```ini
# 300 present requests per summary; 0 disables.
# Values below 60 clamp to 60, values above 3600 clamp to 3600.
dxvk.sd865StatsInterval = 300

# Track compilation wait time, compile time and queue peaks.
dxvk.sd865CompilerTelemetry = True
```

The device logs `DXVK-SD865 counters over ...` after each configured number of **CPU present requests**. Data includes draws, compute dispatches, render passes, pipeline barriers, queue submissions, CPU waits for GPU/CS synchronization and cumulative compiler task progress. CPU present requests are **not proof of physical frames delivered**. This is a scoped approximation for detecting unusually expensive rendering/queueing patterns, not a substitute for RenderDoc or Android SurfaceFlinger timestamps.

The shader worker telemetry prints one summary per 128 completed shader compilation jobs and a final summary after worker shutdown, including aggregate queue wait, compile work and peak pending/latencies. This uses CPU wall-clock timings for individual jobs; concurrent compile work overlaps, so summed durations are **not** wall-clock duration for the whole run. Runs terminating abnormally may lack the final shutdown summary. It does not skip or reorder compilation work.

### Parsing a DXVK log

```shell
python3 tools/sd865_telemetry.py /path/to/dxvk.log
python3 tools/sd865_telemetry.py /path/to/dxvk.log --json > sd865-results.json
```

The parser produces totals per present request, latest compilation snapshot and an optional shutdown summary. Save a separate result for each game scene, driver/build, temperature regime and worker-count setting. For tests, use `python3 -m unittest discover -s tests -p "test_sd865_telemetry.py"`.

Do **not** compare raw totals from runs with different numbers of presents; compare normalized per-present metrics and independent actual frametime/visual-correctness capture. The render-pass counters can identify a likely GMEM pressure cause, but cannot directly measure GMEM bandwidth or render-pass cache flush cost.
