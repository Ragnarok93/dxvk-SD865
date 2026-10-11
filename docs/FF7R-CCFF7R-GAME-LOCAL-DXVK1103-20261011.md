# Crisis Core Reunion: selected DXVK 3.1.1 is NOT the Vulkan DLL actually executing

**Evidence date:** 2026-10-11. User reported Crisis Core Final Fantasy VII Reunion boots and runs with “the 3.1.1 driver” selected in GameNative. Source: user-provided `wine_debug.log (2).txt` (116,874 lines). The original log is **not committed** because it contains private local identifiers. This note summarizes tightly scoped technical evidence.

## Decisive actual loaded DXVK version

The game's Wine Vulkan trace (line 1231) reports:

```text
0148:trace:vulkan:vkCreateInstance Engine name "DXVK", engine version 0x40a003.
0148:trace:vulkan:vkCreateInstance API version 0x401000.
```

`0x40a003` decodes by Vulkan's version encoding to **1.10.3**. This is an **exact source match** for [upstream DXVK v1.10.3 `src/dxvk/dxvk_instance.cpp`](https://github.com/doitsujin/dxvk/blob/v1.10.3/src/dxvk/dxvk_instance.cpp) (`appInfo.engineVersion = VK_MAKE_VERSION(1, 10, 3)`, `appInfo.apiVersion = VK_MAKE_VERSION(1, 1, 0)`). In contrast, [DXVK v2.7.1](https://github.com/doitsujin/dxvk/blob/v2.7.1/src/dxvk/dxvk_instance.cpp) sets `VK_MAKE_API_VERSION(0, 2, 7, 1)` => `0x807001`, and [DXVK v3.1.1](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/dxvk/dxvk_instance.cpp) sets `VK_MAKE_API_VERSION(0, 3, 1, 1)` => `0xc01001`. The requested Vulkan version `0x401000` is also Vulkan 1.1, exactly matching upstream 1.10.3 (and not the 1.3 minimum of DXVK v3.1.1).

The same Wine log loads **game-local** native DLLs instead of the GameNative-configured Wine system DLLs:

```text
A:\CCFF7R\Binaries\Win64\dxgi.dll         (line 890)
A:\CCFF7R\Binaries\Win64\d3d9.dll         (line 892)
A:\CCFF7R\Binaries\Win64\d3d11.dll        (line 894)
```

The version inferred from the Vulkan application header is **strong runtime evidence**, not a SHA256 proof of the bytes of the DLLs (a custom fork could technically preserve an upstream version constant). The close agreement of both `engineVersion` and `apiVersion` with upstream DXVK 1.10.3 and game-local DLL precedence makes that overwhelmingly the correct attribution. It is unsafe to claim DXVK 3.1.1 works from GameNative's selected version.

## What successfully ran

- The actual shipping game process `A:\CCFF7R\Binaries\Win64\CCFF7R-Win64-Shipping.exe` loaded FEX's `libarm64ecfex.dll` and game-local DXVK DLLs, entered Wine's Vulkan bridge.
- The physical device is `Wrapper(PurpleVK-public Adreno (TM) 650 (git-62ac221a33)/unknown)`, with underlying selected Turnip T30 per user settings.
- Wine enumerated `VK_KHR_maintenance5` in its Vulkan **host** and **client** physical-device extension lists (around lines 1359, 1586 and 1752). This alone does **not** prove that the `maintenance5` boolean feature is supported.
- `vkCreateDevice` proceeded (line 1889+), requesting **23** client device extensions. Its enabled list **does not include** `VK_KHR_maintenance5`, `VK_KHR_maintenance6`, or `VK_KHR_8bit_storage`.
- Subsequent logs show **6876** `QueueSubmit` occurrences, **904** `QueuePresent` occurrences, **455** `AcquireNextImage` occurrences and swapchain operations. These are Wine tracing occurrences across multiple wrapper/Wine logger stages rather than exact unique physical-frame counts; they prove substantial GPU rendering activity, not a frame rate or visual correctness. User independently confirms the game boots/runs.
- LSFG Vulkan layer is **active** (frame generation enabled, `Multiplier: 4`, adaptive mode, output FPS cap 120, log lines 1275–1285), so this is not a pure DXVK/FEX performance reference.
- The log contains no `FF7R-8BIT:` or `FF7R-M5:` diagnostics markers. The actual wrapper library named in the loader is `libvulkan_wrapper.so`; its identity cannot be uniquely attributed from that name.
- Wine produced `map_image_into_view ... noexec filesystem?` for game-local DXGI/D3D9/D3D11 text segments (887–894) but DLLs loaded and many Vulkan calls followed. Near shutdown, two Wine SEH “invalid frame” reports occur *after* X connection broken notifications; these do not prove GPU device initialization failure.

## Consequences for FFVII Remake and DXVK 3.x

- **Do NOT conclude** “Crisis Core runs on DXVK 3.1.1 and FFVII Remake does not” from UI selection alone. The true comparison is *Crisis Core with game-local DXVK engine 1.10.3* versus *FFVII Remake with a different, separately confirmed DXVK DLL and stricter required features*.
- The FFVII Remake 3.1.1 log **already directly confirms** the T30 wrapper reports `storageBuffer8BitAccess=false`. The previous dedicated FF7R raw-vs-wrapper probe independently reported underlying Turnip `raw_storage8=0` and `wrapper_storage8=0`.
- A separate FF7R 2.7.1 GPL-async log rejected the wrapper over `maintenance5`. The Crisis Core log demonstrates that the extension name exists in Wine's advertised extension enumeration, but the **feature bit and device-specific driver/feature chain still require audit**. The new opt-in `FF7R-M5` audit WCP is designed to distinguish raw ICD feature 5, wrapper feature 5 and extension exposure. Do not spoof missing features.
- To **really** A/B test Crisis Core with configured DXVK 3.1.1, first back up/rename the three game-local `dxgi.dll`, `d3d11.dll`, `d3d9.dll` (do not delete; beware game-specific mods). Then relaunch once with the selected DXVK WCP and inspect `vkCreateInstance` engine version, normal DXVK `Game` + `DXVK` log lines, and Vulkan adapter result. This test is optional and reversible and needs **no ADB**; use the user's accessible in-game/Android file manager.
- Keep a proven working older DXVK for CCFF7R and a version-attributed working FF7R renderer separately. Avoid benchmarking against a mislabeled game-local DLL.

## Immediate next engineering checks

1. Confirm that new DXVK/FEX WCP builds propagate correctly without game-local overrides; improve Phase-0 classifier to extract `DXVK` Vulkan engine version from Wine `vkCreateInstance` and flag mismatch with selected DXVK.
2. Separate Vulkan extension **listed** from Vulkan feature **enabled** in technical reports.
3. Disable LSFG and excessively verbose Wine `+vulkan` tracing for clean FPS measurements, but retain output for compatibility diagnosis.
4. Complete the separate `FF7R-M5` raw-versus-wrapper feature audit before considering a driver compatibility patch. Inspect runtime DXVK log files independent of Wine if `DXVK_LOG_PATH` is defined.
