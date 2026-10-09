# Using the DXVK-SD865 foundation build

Scope: current Mesa Turnip / Adreno 650 (Snapdragon 865), including community forks that report `VK_DRIVER_ID_MESA_TURNIP`.

**Phase-0 state:** detection, targeted capability logs and optional worker scheduling are implemented. No shader or resource-binding semantics are changed. No frame-rate gain has yet been measured.

## New `dxvk.conf` options

```ini
# -1=auto, 0=disabled, 1=force on Qualcomm Turnip (diagnostic only).
dxvk.sd865Profile = -1

# Log detected driver and selected core/extension capabilities (only Qualcomm Turnip).
dxvk.sd865Diagnostics = True

# Opt-in experiment: 0=unchanged upstream scheduling, 1..8=worker count.
dxvk.sd865CompilerThreads = 0
```

To A/B test shader compilation scheduling, try `dxvk.sd865CompilerThreads = 2`, `3` and `4` on **the same Turnip driver, game, resolution, temperature and FEX setup**. Restart the application for each run. Restore to `0` for the untouched scheduler behavior. An explicit `dxvk.numCompilerThreads` override **always wins** and disables the SD865-specific worker override.

`dxvk.sd865Profile = 0` disables detection/tuning but still allows passive driver logging when diagnostics are enabled. The explicit value `1` can force the experimental profile if a Qualcomm Turnip fork changes the Adreno 650 device name; it will *not* activate on another Vulkan vendor or a proprietary Qualcomm driver. Do not force this mode on an A660/A730; the diagnostic line warns if hardware identification was not verified. Only turn on optional worker tuning on a verified Adreno 650.

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
- Upstream `.github/workflows/artifacts.yml` packages the Windows PE and native Linux variants. These are **not** ARM64EC binaries nor validated `.wcp` files. Runtime tests on Adreno 650 remain required before release.
- Test compile/run locally if desired: `g++ -std=c++17 -Wall -Wextra -Werror -pedantic tests/sd865_policy.cpp -o /tmp/sd865-policy-tests && /tmp/sd865-policy-tests`.

The `dxvk.sd865CompilerThreads` experiment is intentionally opt-in until measurements justify an automatic policy.
