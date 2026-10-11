# FFVII Remake — raw Turnip / Vulkan-wrapper 8-bit feature audit

**Status (2026-10-11):** The FF7R-specific GitHub Actions workflow was repaired and has passed Python unit tests and its pinned source-patch step; the latest CI wrapper build and Android device test require separate successful completion. No evidence of genuine Adreno 650 8-bit storage support has been obtained.

## What this test proves—and does not prove

The experimental wrapper is compiled from **pinned** `leegao/mesa-wrapper-CI` source `417776cc61eb137f0f22f24292f528d396c7189a`, with a **read-only** feature query. It records `VkPhysicalDeviceVulkan12Features` obtained directly from the **actual underlying ICD loaded by this wrapper**, and compares those values to the wrapper's own feature table. This does **not** manipulate `vkCreateDevice`, lie about `storageBuffer8BitAccess`, or modify shader compilation. DXVK 3.1.1 can still refuse unsupported A650 hardware.

**Important limitation:** This diagnostic wrapper comes from a different source family than the user's installed PurpleVK T30 binary. It measures the Turnip ICD that the *experimental wrapper* loads; it **cannot automatically prove that the original PurpleVK wrapper** has identical feature conversion or ABI. The underlying Turnip build must be kept identical and the wrapper switch must be made explicit. No successful 8-bit shader conformance is inferred from a capability report.

## Install only after successful CI

1. Open [FF7R PurpleVK real 8-bit storage audit wrapper workflow](https://github.com/Ragnarok93/dxvk-SD865/actions/workflows/ff7r-wrapper8bit-verified.yml) and confirm the **latest** run has **success** in all steps, particularly `Unit tests`, `Build Vulkan wrapper`, `Package opt-in GameNative Wrapper overlay WCP`, and `Upload experimental wrapper`. On failure, **do not install** a file from an older run.
2. Download the `FF7R-PurpleVK-raw-8bit-audit-aarch64` artifact, extract it, verify `SHA256SUMS` and install `FF7R-RawICD8-<sha>.wcp` via GameNative **Contents** as **Wrapper**, not as Turnip or DXVK. This is only a partial replacement for the wrapper's `libvulkan_wrapper.so` and relies on existing hook libraries and an ICD.
3. **Back up your working GameNative wrapper profile and know how to restore it.** GameNative's `ContentsManager.applyContent` copies the selected component into a shared `imagefs/usr/lib/libvulkan_wrapper.so` target. This is **not guaranteed to be isolated to FF7 Remake or a single container**. A third-party wrapper ABI may differ. If switching to the diagnostic build causes a crash or non-boot, immediately reselect/reapply the original wrapper profile (or reinstall it) before testing other games. Do not alter the system/vendor Vulkan driver, root, or flash firmware for this test.
4. Keep original *Mr. Purple T30* Turnip/ICD version selected, record its SHA/build string, and test only FF7 Remake. Keep DXVK 2.7.1 WCP available for rollback; using DXVK 3.1.1 only diagnoses the startup check. Disable LSFG. Ensure GameNative Wine debug log capture is on.
5. Set these only for the diagnostic session:
   ```text
   WRAPPER_FF7R_FEATURE_AUDIT=1
   WRAPPER_LOG_LEVEL=info
   WRAPPER_LOG_FILE=stdout
   WRAPPER_DIAG=1
   GN_DXVK_DIAGNOSTICS=1
   DXVK_LOG_LEVEL=info
   ```
   Note: `GN_DXVK_DIAGNOSTICS` requires a GameNative build with the opt-in logging fix. `WRAPPER_LOG_FILE=stdout` can write to Wine/launcher output, but capture depends on GameNative's process logging; if the marker is absent, do not conclude raw driver support is absent. If available, `WRAPPER_LOG_FILE` can instead specify an **existing, accessible writable file path** for the native wrapper process.
6. Run the game once. Export `wine_debug.log` using GameNative → Settings → Debug → View game debug log / Save. Include `ff7remake__dxgi.log` and/or `ff7remake__d3d11.log` from DXVK's configured log directory. **Do not relaunch before saving the log**, since a new capture can replace it.

## Interpret the log

The custom marker looks like this (example format, **not observed data**):

```text
FF7R-8BIT: raw_storage8=0 wrapper_storage8=0 raw_shaderInt8=1 wrapper_shaderInt8=1 raw_uniform8=0 wrapper_uniform8=0 raw_pushConstant8=0 wrapper_pushConstant8=0
```

Download the repo source and run:

```bash
python3 -m unittest discover -s tests -p test_ff7r_turnip8_audit.py -v
python3 tools/ff7r_turnip8_audit.py wine_debug.log ff7remake__dxgi.log --json-out ff7r-raw-storage8.json
```

| Verdict | Meaning | What to do |
| --- | --- | --- |
| `no_valid_audit_marker` | Probe never logged or capture missing | Verify selected `.wcp`, environment, log capture; no GPU conclusion |
| `driver_reports_storage8_unavailable` | Raw loaded ICD and experimental wrapper both show 0 | No valid 3.1.1 support with this ICD; optimize DXVK 2.7.1 instead |
| `raw_wrapper_feature_mismatch` | Feature flags differ | Inspect wrapper feature propagation **on this experimental build**; do not blindly force fields |
| `both_report_storage8_available_not_conformance_proof` | Both report 1 | First run 8-bit SSBO shader conformance and full DXVK required feature audit |
| `conflicting_driver_or_session_results` | Multiple contradictory devices/runs | Split logs by session/device, do not assume A650 support |

Stop and restore working wrapper immediately on device crashes, Vulkan validation failures, abnormal memory usage, or lost graphics.

## Next mandatory gates for any candidate driver

Reported feature == 1 -> enable it at `vkCreateDevice` -> compile and run correct SPIR-V storage-buffer 8-bit loads/stores -> assess required extensions and Vulkan limits for DXVK 3.1.1 -> compare FF7 Remake rendering/cutscenes and performance against known working DXVK 2.7.1 with LSFG off.

No source-based read-only audit can replace an actual device measurement or Vulkan shader-conformance run.
