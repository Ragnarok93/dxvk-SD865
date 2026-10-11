# FFVII Remake / Adreno 650: phone-only DXVK memory allocation diagnostics

**Scope:** Opt-in diagnostics for the DXVK 2.7.1-derived `dxvk-SD865` fork. No Vulkan feature spoofing, memory-size changes, forced 4-GiB override, eviction tweaks, or modified allocation/retry policy.

**2026-10-11 revision:** The user's latest 732-line Wine log and six-line D3D11 log again contained the ~21.33-MiB allocation failure at `heap.size=4096 MiB`, `DXVK allocated=3972 MiB`, `driver budget=4751 MiB`, but zero `DXVK-SD865-ALLOC` markers. The initial released WCP contains marker strings in its compiled PE DLLs, so the run could have used another DXVK or not propagated `DXVK_SD865_ALLOC_TRACE=1`. The self-identifying diagnostic WCP eliminates the latter prerequisite and confirms activation with an unconditional single startup marker. The later critical-section 60-second timeout and X-server shutdown do not independently prove a driver error code.

## Confirm artifact before installation

Only import a successful `FF7R SD865 DXVK 2.7.1 allocation trace WCP` [GitHub Actions artifact](https://github.com/Ragnarok93/dxvk-SD865/actions/workflows/ff7r-alloc-trace-dxvk271-wcp.yml). GitHub wraps artifact contents in a ZIP; **extract ZIP first** and import the inner `dxvk-ff7r-allocdiag-dxvk271-<commit>.wcp` into GameNative as a **DXVK** content package. Do not import as Wrapper or Graphics Driver. A unique version name avoids reusing a cached selected DLL set. Keep working DXVK 2.7.1 available for immediate rollback.

The WCP includes both Win64 (`x64`) and Win32 (`x32`) DXVK DLLs. It is not a Turnip, Vulkan wrapper, FEX or GameNative APK update.

## GameNative container setup (no ADB)

1. In GameNative Contents Manager import the inner `.wcp` file, and select `ff7r-allocdiag-dxvk271-...` in the container's **DXVK Version** selector.
2. Keep the same Turnip T30 and FEX2610 settings as a single-variable test. Disable LSFG and vkBasalt/CAS for the first baseline if possible.
3. **No allocator-specific environment variable is required in the updated self-identifying WCP.** Selecting the uniquely named diagnostic DXVK version enables failure-only capture. You may retain:
   ```ini
   DXVK_LOG_LEVEL=error
   ```
   `DXVK_SD865_ALLOC_TRACE=0` disables allocator tracing if you want to test a control run, but leave it unset otherwise. `DXVK_LOG_PATH` may remain directed to an accessible Downloads directory. DXVK's existing Wine debug transport also emits error-level messages to GameNative's process capture.
4. In **Settings → Debug**, enable **Enable Wine Debug Logs**. Disable Wine `+vulkan`, `+loaddll`, etc. trace channels; they are not required to capture `DXVK-SD865-ALLOC` and otherwise generate million-line logs.
5. Launch FFVII Remake **once**, reproduce the allocation failure, export **Settings → Debug → View game debug log → Save**, and collect `ff7remake__d3d11.log` if easily accessible in your DXVK log directory. Upload both files in ChatGPT. **No ADB**, logcat commands, rooting or Android/data browsing.
6. Revert to working DXVK version after the test if gameplay stability worsens. Remove the diagnostic variable for normal use.

## Expected output

The updated diagnostic WCP prints this **one-time build/activation proof** when its allocator is initialized. If absent, the WCP has not loaded the running game or its stdout/stderr logging is not captured:
```text
err: DXVK-SD865-ALLOC state=diagnostic_wcp_loaded capture_enabled=1 heap_count=1 heap0_size_bytes=4294967296 ...
```

The numbers in this example are **illustrative**, not observed by the new WCP. Then, only when an allocation attempt fails, the driver emits an event:

```text
err: DXVK-SD865-ALLOC stage=driver_retry first_attempt_id=403 retry_attempt_id=404 first_vkresult=-2 first_name=VK_ERROR_OUT_OF_DEVICE_MEMORY retry_vkresult=-2 retry_name=VK_ERROR_OUT_OF_DEVICE_MEMORY recovered=0 requested_bytes=22369792 memory_type=1 heap=0 heap_size_bytes=4294967296 ...
```

This is an **invented example format**, not an observed return code. Values are recorded from real Vulkan results if the feature is enabled, subject to a cap of 128 diagnostic lines per process.

Interpret stages distinctly:

- `driver_retry`: real first and retried `vkAllocateMemory` result, outcome, size, memory type, heap size, DXVK allocator stats, driver budget/usage.
- `budget_guard`: DXVK budget check intentionally skipped a Vulkan driver allocation; `driver_call=0`.
- `pool_exhausted`: no pooled global-buffer allocation could be found after allowed attempts, regardless of reason.
- `dedicated_exhausted`: all permitted dedicated-memory types failed.

Parse exported log on a PC if desired:

```sh
python3 tools/ff7r_alloc_trace_report.py wine_debug.log --json-out alloc_report.json
```

No script is required on the phone; uploading the logs in chat is sufficient for analysis.

## Existing evidence, not a new result

From the user-uploaded 2026-10-11 DXVK D3D11 log, **four** memory allocation failures occurred near 3988–3992 MiB allocated with a reported 4096 MiB heap. The earlier report had a larger 7951 MiB heap. The new error-level trace is intended to establish whether driver return codes show `VK_ERROR_OUT_OF_DEVICE_MEMORY`, `VK_ERROR_OUT_OF_HOST_MEMORY`, another Vulkan result, or an internal budget/pool restriction. The logs also show an eventual DXVK command-stream exception; do not interpret its cause as proven until return codes and a driver-side stack are available.

The separate `pluvia_crash_2026-10-06_06-51-57.txt` reports an **older GameNative Java JNI `UnsatisfiedLinkError`** and is not a stack trace of this DXVK memory failure.
