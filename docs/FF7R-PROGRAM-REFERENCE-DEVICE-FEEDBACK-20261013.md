# FF7R program-reference device feedback — 2026-10-13

User selected mesa-turnip-perf-sd865-program-reference-main.zip and confirms manual termination. Prior user-selected Cortex-A77 control also ended manually, but used different diagnostic logging. Do not claim a matched performance A/B.

## Confirmed initialization and presentation

- DXVK-FF7R-PHASE0 d3d11_device_created appears twice, feature level 11_0.
- first_dxgi_present records d3d12_queue=0 and sync_interval=0. This confirms the custom instrumented DXVK D3D11 path, not a unique source commit stamp.
- DXVK version 2.7.1, x86_64 GCC 16.2.0; wrapper driver still masks underlying exact Mesa commit. LSFG separately identifies backend as turnip Mesa driver, driver_id=18, Vulkan 1.3+ / core-1.3-sync2.
- vkBasalt instance/device layer inserted, effects=cas, casSharpness=1.0, enableOnLaunch=True.
- LSFG target ff7remake_.exe: Resident/Off, multiplier 1; layer remains installed and hooks WSI as required by the user.
- 83 sampled LSFG present-result entries all return result=0 (VK_SUCCESS). Last sampled sequence is 8520; no elapsed-time denominator or real-frame cadence data, so this is not FPS.
- No recorded Vulkan device-lost, device/host-memory OOM or unhandled Wine exception.

## Important downstream presentation behavior

DXVK's presenter reports 1280x720, immediate mode, four images. LSFG logs both swapchain creations with requestedImages=4 but legacy-headroom policy adds three images (residentMultiplier=4). Downstream create requests seven images, presentMode=1; present-contract names fifo_backend=mailbox. Vulkan enum 0=immediate, 1=mailbox, 2=FIFO. This captures application request versus layer-selected downstream creation, not display timing or proven scanout/latency.

LSFG resident-off mode prebuilds an AHB frame-generation context and 16 adaptive-flow states. Each logged resource build reports 2250 added images, 93237248 image bytes (88.918 MiB), 240 buffers (15360 bytes), 9135 descriptor sets and shared pipelines/samplers. Prebuilds take 108.689 and 121.824 ms. This is initialization/recreation work, not measured steady-state overhead. Do not sum both builds into peak live memory. Opaque-fd external semaphores unsupported; sync-fd supported, completion path host-wait. No evidence here that every normal frame blocks in that fallback.

## New shutdown fault

After six X connection broken messages, final line is FORTIFY: pthread_mutex_lock called on a destroyed mutex. User confirms manual stop. This is a real native lifetime/shutdown error, but the mutex address is not a code address/backtrace and cannot identify the owning component. Do not attribute it to Turnip's program-reference patch, DXVK's lock backport, LSFG or FEX without native stack/maps evidence. Prior control capture lacks the message; differing logging/shutdown timing prevents a regression verdict. Keep shutdown validation pending.

## Other issues and comparison limits

- Four attempts to load VK_LAYER_UTIL_UtilLayer fail because libutil_layer.so is absent. Rendering continues, so this did not prevent device/present setup. Establish whether the layer is required before changing its configuration.
- Wine NtUnlockFile/fixme flood is now suppressed: zero matching messages, log is 125465 bytes / 1379 lines versus 10854483 bytes / 190200 lines for prior control. This proves reduced recorded verbosity, not implementation of keyed unlock or a measured speedup.
- Startup budget 5.20/5.10 GiB versus prior 4.62/4.60 GiB. These are budget snapshots, not allocation savings attributable to the patch. System-memory conditions differ.
- Graphics/transfer queue remain (0,0); GPL and eight compiler threads unchanged.
- EDID/colorimetry warnings and separate GameNativeDNS loader issue remain.
- No FPS, duration, real-frame median or p95/p99 samples. Image correctness not established by logs.

## Next evidence

Repeat the Cortex-A77 control and program-reference candidate with identical low-noise logging, DXVK, LSFG/vkBasalt settings, scene, warmed caches and thermals. Keep layers enabled in-container and FG off in-game. Capture real-frame timing statistics, not present sequence counts. For shutdown attribution obtain Android logcat/native abort backtrace around the manual stop; Wine's mutex address alone is insufficient. No source behavior changed based on this capture.

Input SHA256:
- ff7remake__d3d11.log: 45e3e5d5278a3d47f04ff7179bbf57ef7b7305b284680b249ca72484367d3ed8
- ff7remake__dxgi.log: 57689027026681edd584f87f51e7df889965e5f691456d97f058223964bc9301
- wine_debug.log.txt: d2343ce283f1521d655eadfe2691866ad93e539702fc399f9a38b73b49ca2319

No raw command lines or authentication fields are copied into this report.
