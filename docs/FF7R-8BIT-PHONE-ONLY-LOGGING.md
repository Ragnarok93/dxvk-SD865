# FF7 Remake raw Turnip 8-bit audit — no ADB, no filesystem browsing

**As of 2026-10-11:** Diagnostic Wrapper WCP source emits early and capability markers directly to **stderr**, which GameNative's existing `ProcessHelper.createDebugThread(process.getErrorStream())` appends to its own Wine debug log when **Enable Wine Debug Logs** is enabled. This requires **no new GameNative code, Shizuku, root, ADB, shell commands, manually accessible Android/data paths, WRAPPER_LOG_FILE, WRAPPER_DIAG, or WRAPPER_LOG_LEVEL**.

**Verified CI build:** [GitHub Actions run 38137851393](https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38137851393) is successful. Source SHA `c05eb99bb904ad33de6e0bbd43533f4df5f38225`. The extracted `FF7R-RawICD8-c05eb99bb904.wcp` is an XZ/TAR package with the `Wrapper` profile at the archive root and has verified SHA-256 `76a9582a96b6c5dfc815294283045a922f5da2d328d580dd6122f379c210ab4e`. It is build-verified, **not** device-runtime-verified.

## Phone-only workflow

1. Back up existing GameNative **Wrapper** profile (the Wrapper library is shared) and keep a known-working DXVK **2.7.1** WCP. The new experiment is a wrapper, **not** a replacement DXVK package.
2. From the **successful** [FF7R Vulkan wrapper audit workflow](https://github.com/Ragnarok93/dxvk-SD865/actions/workflows/ff7r-wrapper8bit-verified.yml), extract the GitHub artifact ZIP, then **import the extracted FF7R-RawICD8-<sha>.wcp** via **Contents Manager → Wrapper**. The outer GitHub ZIP will show *File cannot be recognized*.
3. Select/reapply the imported diagnostic **Wrapper**. Use your usual Turnip T30 and **DXVK 2.7.1** to ensure Vulkan initialization can reach the feature query. Do not require DXVK 3.x just to obtain a 8-bit-storage report.
4. In GameNative **Settings → Debug**, enable **Enable Wine Debug Logs** (the existing preference).
5. Launch FFVII Remake once. Even if it fails during Vulkan initialization, early marker should identify whether the diagnostic wrapper loaded. **Do not launch the game a second time before exporting**, because GameNative deletes/recreates the previous Wine log at launch.
6. Go to **Settings → Debug → View game debug log → Save**. Save as `wine_debug.log.txt` to Downloads and attach in chat.

## What the log proves

When the wrapper receives `vkCreateInstance`, it writes a line directly to stderr:

```text
FF7R-8BIT: wrapper_instance_probe
```

This proves our experimental wrapper reached Vulkan instance creation, even if device enumeration subsequently fails. When it queries the Vulkan physical device, it directly calls the selected raw Turnip ICD and prints:

```text
FF7R-8BIT: raw_storage8=0 wrapper_storage8=0 raw_shaderInt8=1 wrapper_shaderInt8=1 raw_uniform8=0 wrapper_uniform8=0 raw_pushConstant8=0 wrapper_pushConstant8=0
```

These are **illustrative field names/values only**, not S20+ measurements. The probe does not modify Vulkan feature flags. The `FF7R-8BIT` physical device line identifies real driver-versus-wrapper feature reporting, NOT correct SPIR-V 8-bit shader behavior or total DXVK 3.1.1 compliance.

If neither marker occurs, **do not infer** that the hardware lacks storage8. Confirm the diagnostic Wrapper profile was actually *applied* and the game's Vulkan path used the wrapper, and check that Wine debug logging was enabled. A DXVK log showing an adapter but no wrapper marker usually means the experimental Wrapper is not on that specific Vulkan loader/ICD path.

## Why Wine UI export works

`Ragnarok93/GameNative/app/src/main/java/com/winlator/core/ProcessHelper.java`: when debug callbacks exist, `exec()` reads both the native process standard output and standard error through `createDebugThread`.

`Ragnarok93/GameNative/app/src/main/java/app/gamenative/ui/screen/xserver/XServerScreen.kt`: when `enableWineDebug` is true, `ProcessHelper.addDebugCallback` writes each captured line into `context.getExternalFilesDir(null)/wine_logs/wine_debug.log`.

`Ragnarok93/GameNative/app/src/main/java/app/gamenative/ui/screen/settings/SettingsGroupDebug.kt`: `View game debug log` and the Save action use Android's file picker to export that log to user-chosen storage.

The diagnostic wrapper has **two** direct `fprintf(stderr, ...); fflush(stderr)` outputs, independent of third-party `WRAPPER_LOG_FILE` permissions or log verbosity controls. Generated diagnostics are only a few lines per Vulkan instance/physical device; there is no per-frame instrumentation.

## Fallback

If you prefer, use GameNative **Settings → Debug → Save App Logs** in addition to Wine debug log, but the latter is the expected primary location for the new marker. The native stderr capture must be enabled; **app-only logs cannot guarantee a Vulkan capability marker**.

**Test disposition:** build success does NOT establish the exact T30 binary supports 8-bit SSBO. Do not install a WCP from a failed CI run. This diagnostic is a temporary Wrapper overlay and should be reverted after the capture.


## 2026-10-11: S20+ container screenshot + third Wine log investigation

User supplied five GameNative FF7 Remake settings screenshots plus a 1,910-line Wine log (the same key event counts and tail as the preceding capture; not a new raw Vulkan sample).

**Verified selections:** Graphics Driver = `Wrapper-FF7R-RawICD8-c05eb99bb904`; Graphics Driver Version = `Turnip Adreno Driver T30`; Display Renderer = Vulkan; DX Wrapper = DXVK; DXVK Version = `2.7.1-1-gplasync-0`; Use AdrenoTools Turnip enabled; FEXCore = `2610-GameNative-FF7R-Phase0-71b9...`; FEXCore preset = FF7R-Balanced. User env includes `DXVK_FF7R_PHASE0=1`, `FEX_FF7R_PHASE0=1`, `GN_DXVK_DIAGNOSTICS=1`, `DXVK_LOG_LEVEL=info`, and a `DXVK_LOG_PATH` targeting D: storage.

**Correct the earlier inference:** GameNative intentionally **selects** custom Wrapper WCPs in the *Graphics Driver* dropdown. Source `XServerScreen.kt` lines 6043–6065 derives the `Wrapper-*` selected string, looks up the matching installed `ContentProfile`, and applies it to the imagefs. Keeping Turnip T30 as `Graphics Driver Version` and AdrenoTools enabled is an intended wrapper+underlying-driver configuration. This screenshot is NOT a mislabeled DXVK WCP or proof that the wrapper is the wrong graphics driver.

**Source-derived risk:** Wrapper content is only reapplied if `ALWAYS_REEXTRACT`, first launch, or `mainWrapperSelection != lastInstalledMainWrapper`. This cached state can leave an old library installed if content was changed while the same wrapper remained selected. For retry, intentionally switch to the known working stock Wrapper, save, then reselect the **new** uniquely versioned audit Wrapper, save. This forces reapplication without using ADB.

**Log:** 0 `FF7R-8BIT`, 0 `FEX-FF7R-PHASE0`, 1536 `NtUnlockFile Unimplemented yet parameter`, native D3D11/DXGI loads, ARM64EC FEX load, X-server closed. Does not prove the wrapper failed to load: v1 diagnostic only printed from `vkCreateInstance` and device creation, and the game might not reach Vulkan. Nor does Wine-log absence of DXVK text prove DXVK init failed: `DXVK_LOG_PATH` routes normal DXVK logger output to its own files and the user did not provide those files.

**Improvement:** Third marker `FF7R-8BIT: wrapper_library_loaded` generated by a one-time ELF constructor in `tools/ff7r_wrapper8bit_patch.py` emits to stderr as soon as the Vulkan wrapper library is loaded, independent of vkCreateInstance. Compile and verify all three marker strings appear inside the packaged ARM64 .so. The diagnostic does NOT change Turnip capability flags.

**Secondary config items:** `TU_DEBUG=noconform` should be removed only for a controlled *conformance* comparison; `vkBasalt` CAS is active, so turn it off for a clean rendering baseline. `WRAPPER_MAX_IMAGE_COUNT=0`, WINEESYNC, FEX cache, ZINK and mailbox/FIFO variables are not evidence of the absent diagnostic markers. No cause for Wine `NtUnlockFile` spam can be established from a single un-timed log.

**Phone-only next capture:** Select working Wrapper, save, then uniquely versioned library-constructor diagnostic Wrapper, save; keep T30 and DXVK 2.7.1, enable Wine debug log; run once, export via GameNative Settings → Debug → View game debug log → Save. Interpret: library marker missing = library not loaded / pipe capture missing; library present + instance missing = no Vulkan instance call (or entrypoint bypass); instance present + raw missing = physical device initialization incomplete; raw present = capability comparison valid for this loaded ICD. Avoid ADB.
