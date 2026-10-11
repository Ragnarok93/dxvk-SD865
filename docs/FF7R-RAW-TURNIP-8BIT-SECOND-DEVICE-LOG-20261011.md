# FFVII Remake raw-storage8 audit: second user log — inconclusive

**Received 2026-10-11 11:46 UTC.** User-supplied `wine_debug.log.txt`, 1,910 lines, 121,695 bytes. Do not commit the original log because it includes local identifiers. This document is derived from that one session.

## Verified observations

- FFVII Remake launched as `A:\\End\\Binaries\\Win64\\ff7remake_.exe` in Wine's experimental **ARM64EC** mode (line 303).
- Wine loaded `libarm64ecfex.dll` in the game process (305), native `dxgi.dll` (340) and native `d3d11.dll` (342). Game-local `XINPUT1_3.dll` was also loaded (338).
- Exactly **0** occurrences of `FF7R-8BIT:`, **0** `DXVK:`, **0** `vulkan`, and **0** `FEX-FF7R-PHASE0` in this file. DLL load events do NOT prove successful DXVK device creation or that the test Wrapper WCP is applied.
- `0154:fixme:file:NtUnlockFile Unimplemented yet parameter` repeats **1,536 times** (~80% of log lines), starting line 370 and lasting until line 1906. This is Wine file-lock API logging on one thread. It may inflate log size/performance overhead; cannot establish a file-lock deadlock or the cause of an observed hang from this text alone.
- `vkBasalt` CAS sharpening enabled (lines 187-190); disable it for a clean A/B test, but no causal link to current stall is proven.
- Capture ends with four `X connection to :0 broken (explicit kill or server shutdown)` messages, lines 1907-1910. No application exception, DXVK feature rejection, Vulkan device selection, or successful present is visible.
- The previous separate 3.1.1 capture reported `storageBuffer8BitAccess` unavailable at adapter enumeration. **This second log supplies no new raw-driver capability values and cannot confirm or overturn that result.**

## Narrow next test: known-working 2.7.1 to force a Vulkan query

1. If the new Wrapper WCP caused non-boot, **restore the previously working Wrapper first**. Wrapper overlay can affect GameNative shared library state across containers. Avoid changing both DXVK and Wrapper simultaneously without control.
2. For a controlled diagnostic test, keep the *experimental audit wrapper* selected only if the user can safely restore the original. Use the known-working **DXVK 2.7.1** WCP, the same Turnip T30 driver, LSFG disabled and vkBasalt disabled. This should reach Vulkan farther than failing 3.1.1 if the wrapper is compatible.
3. Environment:
   ```text
   WRAPPER_FF7R_FEATURE_AUDIT=1
   WRAPPER_LOG_LEVEL=info
   WRAPPER_DIAG=1
   WRAPPER_LOG_FILE=/storage/emulated/0/Android/data/app.gamenative/files/ff7r-8bit.log
   GN_DXVK_DIAGNOSTICS=1
   DXVK_LOG_LEVEL=info
   ```
   The examined reference wrapper `src/vulkan/wrapper/wrapper_log.c` uses `WRAPPER_LOG_FILE` as an absolute filename. Its *default* log directory `/sdcard/wrapper/logs` may be blocked by Android 13 scoped storage; the GameNative app-specific external files directory is preferable because it is normally writable by the app. This environment syntax is native Linux/Android, not the Wine D: path. Capturing this separate file avoids treating Wine stdout suppression as absence of wrapper execution.
4. After a *single* launch, **do not relaunch before exporting**. On USB ADB:
   ```bash
   adb shell ls -l /sdcard/Android/data/app.gamenative/files/ff7r-8bit.log
   adb pull /sdcard/Android/data/app.gamenative/files/ff7r-8bit.log .
   ```
   If file does not exist, the test is **not** evidence of no hardware support: wrapper may not have loaded, its logger may not have initialized, or storage permissions may block it. Collect GameNative app logs/logcat and check that selected Wrapper profile is actually applied.
5. If 2.7.1 runs but still no `FF7R-8BIT`, distinguish an inactive test wrapper from missing environment/log capture before changing Turnip. If marker appears, classify with `python3 tools/ff7r_turnip8_audit.py <wrapper-log>`. If raw bit 0, DXVK 3.1.1 remains unsupported on that driver regardless of wrapper. If raw bit 1, proceed to shader conformance and all DXVK 3.1.1 feature checks.
6. Only after successful baseline + marker attempt compare 3.1.1 as the *sole changed variable*. Avoid interpreting Wine `NtUnlockFile` spam as Vulkan capability evidence.

## Boundaries

Do not force-enable `storageBuffer8BitAccess`, alter Vulkan `apiVersion`, patch FEX JIT, or disable DXVK required-feature checks in response to this second log. It has no raw or wrapped feature data, no kernel fault, and no rendering timing.
