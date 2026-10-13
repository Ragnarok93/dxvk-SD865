# FF7R device run assessment — 2026-10-13

User confirms the selected Turnip profile was sd865-cortex-a77 (control), and the run ended manually. This is a successful reported gameplay smoke test of the selected control combination, not a test of the program-reference candidate or a measured speedup.

Evidence:
- DXGI reports DXVK 2.7.1, x86_64 GCC 16.2.0; Wine loads native d3d11.dll and dxgi.dll from C:\windows\system32, not game-local DLLs.
- D3D11 device creation uses feature level 11_0; advertised maximum is 11_1. No minimum-feature-level rejection.
- Presenter creates a 1280x720 swapchain, immediate present mode, four images. Swapchain resolution does not establish internal game render resolution, nor do four images establish four frames of latency.
- Graphics and transfer both report queue (0,0); no separately selected transfer queue in this capture.
- GPL enabled, eight compiler threads. No compiler-duration or pipeline-count measurements.
- Shared device-local heap 7.76 GiB; startup budget snapshots 4.62 and 4.60 GiB. These are advertised heap/budget values, not actual game usage or guaranteed free RAM.
- No recorded VK_ERROR_OUT_OF_DEVICE_MEMORY, VK_ERROR_OUT_OF_HOST_MEMORY, VK_ERROR_DEVICE_LOST, allocation failure or unhandled exception.
- Wine ends with X connection broken messages; user confirms manual shutdown, so do not classify them as a crash.

Main finding: 189,202 NtUnlockFile 'Unimplemented yet parameter' messages among 190,200 Wine log lines (99.48%); Wine log size 10,854,483 bytes. Upstream Wine's dlls/ntdll/unix/file.c emits this for a nonzero key argument and returns STATUS_NOT_IMPLEMENTED. Exact custom Wine implementation/caller is not identified by this capture. The failed-call loop and logging may consume CPU/I/O, but overhead cannot be quantified here. Suppressing logging does not implement the unsupported operation. Do not attribute the warnings to DXVK, FEX cache, DRM or a specific shader-cache path without a caller trace.

EDID/colorimetry and OpenVR warnings did not prevent device/swapchain creation. The GameNativeDNS EVP_MD_CTX_init/libsqlite loader issue is separate container/DNS integration evidence; not a captured Vulkan failure. Unknown interface queries were followed by successful setup.

Attribution limits: Wrapper(5710), Wrapper driver 26.2.99 masks underlying Turnip provenance. User's selected profile identifies the control operationally, but the logs do not expose Mesa 76b9372, artifact SHA or program-state patch status. DXVK 2.7.1 is not a unique commit stamp. No DXVK-FF7R-PHASE0 markers, real-frame timing samples, FPS averages or p95/p99 data. LSFG/vkBasalt loading/FG state are not observable in these three logs; preserve the user's established settings rather than treating missing strings as disabled layers.

Next comparison: same new DXVK, first matched Cortex-A77 control then program-reference candidate; textures Low, same scene/thermals and equally warmed caches; LSFG/vkBasalt on in-container, LSFG FG off in-game. For timed runs use WINEDEBUG=-all and DXVK_LOG_LEVEL=info. A short attribution run can use WINEDEBUG=-all,+loaddll and DXVK_FF7R_PHASE0=1; markers confirm the custom instrumented D3D11/present path, not a unique backport commit. Capture run duration and real-frame statistics in at least three matched trials per profile. Do not change compiler thread count and driver simultaneously.

Input SHA256:
- ff7remake__d3d11.log: bc6a776e09e75d88e9e8bc4639cd81ff52bb9cec8c8a321d5d1570e39168fe8c
- ff7remake__dxgi.log: 82aeef563b8263d4a4818d9bad792b1c5e36178da56e2e435598faae9a47744d
- wine_debug.log.txt: f6990e1a84f766195d6e8cf7575f926729db90a0e2427510084b376b7f8fe2f1
