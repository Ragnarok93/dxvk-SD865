# FFVII Remake — first DXVK 3.1.1 device evidence (2026-10-11)

**Status:** first on-device startup diagnosis supported by user-supplied `ff7remake__dxgi.log` (22 lines) and `wine_debug.log.txt` (938 lines). Source log files are **not** committed; this note contains only selected technical evidence. **This capture is NOT a performance baseline** and does not validate the separate opt-in DXVK 2.7.1/FEX diagnostic WCPs.

## Confirmed observed behavior

```text
info: Game: ff7remake_.exe
info: DXVK: 3.1.1
info: Found device: Wrapper(PurpleVK-public Adreno (TM) 650 (git-62ac221a33)/unknown) (Wrapper driver 26.2.99)
info: Skipping: Device does not support required feature 'storageBuffer8BitAccess'
warn: DXVK: No adapters found. Please check your device filter settings
err: Failed to initialize DXVK.
```

Selected Wine log positions (one-indexed): 342 / 435 game process startup in Wine experimental ARM64EC; 352 / 437 `libarm64ecfex.dll` loaded; 391–394 / 473–476 native `dxgi.dll`, `d3d9.dll`, `d3d11.dll` loaded; 389 / 471 native game-local `XINPUT1_3.dll` loaded; 540–542 DXVK 3.1.1 startup; 869 host Vulkan device name; 873–881 *actual fatal adapter rejection*. No `d3d12.dll` load, DXVK-FF7R-PHASE0 marker, FEX-FF7R-PHASE0 marker, or successful game DXGI Present evidence is present in the supplied logs.

**API verdict:** `d3d11_attempt_failed_at_vk_adapter_filter`. This is stronger than mere DLL load: DXVK 3.1.1 tried to initialize Vulkan, found the GPU, rejected the feature, and failed. It is NOT `d3d11_dxvk_present_path`, because no D3D11 device/presentation was demonstrated. It is NOT evidence of the D3D12/VKD3D rendering path. The game's generic “DX11 feature level 10 is required” popup may be downstream of failed DXVK device creation; the logs do not prove a D3D11 FL10 implementation bug.

**Other observations:** `esync: up and running`, repeated Wine `fixme:fsync:do_fsync futexes not supported` and `fixme:file:NtUnlockFile Unimplemented yet parameter`, and vkBasalt CAS sharpening. These should be separately benchmarked/correctness-audited once the game renders; they are not established causes of the Vulkan rejection or frame-time regression.

## Root-cause decision tree: no spoofing

1. DXVK 3.x has a hard `storageBuffer8BitAccess` requirement. Confirm with [DXVK driver requirements](https://github.com/doitsujin/dxvk/wiki/Driver-support).
2. Determine the **underlying Turnip driver** feature using a direct/raw `vkGetPhysicalDeviceFeatures2` query (`VkPhysicalDeviceVulkan12Features.storageBuffer8BitAccess` or `VkPhysicalDevice8BitStorageFeatures`) and compare with the **PurpleVK wrapper** output from the same Turnip build. Record reported Vulkan API version, 8-bit-related feature bits, and actual driver/wrapper build identities. The current logs show only the wrapper-facing result, not the real driver's pre-wrapper feature value.
3. If underlying driver reports TRUE but wrapper FALSE: fix **wrapper feature propagation**, preserving Vulkan version/extension/feature consistency and real `vkCreateDevice` feature enablement. Do not mutate DXVK feature checks or force D3D feature levels.
4. If underlying driver reports FALSE: investigate correct 8-bit shader/storage implementation or a conforming alternate graphics driver. Do **not** advertise a capability the device/compiler cannot implement.
5. Re-run the **separate 3.x Vulkan audit** branch `feature/sd865-fl10-diagnostics-20261010` with `DXVK_SD865_DIAGNOSE=1` and `DXVK_LOG_LEVEL=info` to enumerate **all** missing 3.x mandatory features, rather than assuming this is the only blocker. Full audit marker absent from first logs, so no full compatibility conclusion.
6. Preserve the working `DXVK 2.7.1` WCP unchanged. Use the dedicated 2.7.1 Phase 0 instrumentation WCP for successful D3D11 attribution (D3D11 creation + first present) and *then* gather genuine non-LSFG real frame times.

## Relevant independent implementation reference

[An Adreno 660 wrapper project](https://github.com/jtiberius9-spec/vili-wrapper-build) documents the same `storageBuffer8BitAccess` DXVK 3.x rejection and a patch to `src/vulkan/wrapper/wrapper_physical_device.c` in [leegao/mesa-wrapper-CI](https://github.com/leegao/mesa-wrapper-CI/tree/gn_wrapper2). This is a **hypothesis-generating analogue**, not proof that our PurpleVK source has the same defect. Review actual wrapper code, feature querying and feature enabling; don't import the patch unconditionally. Vulkan 1.4 requires the feature, but it can be optional for Vulkan 1.2/1.3 implementations: [Khronos VK_KHR_8bit_storage](https://docs.vulkan.org/refpages/latest/refpages/source/VK_KHR_8bit_storage.html).

## Next milestone

Complete the device feature comparison, recover the full 3.x missing-feature list if possible, and obtain a **working DXVK 2.7.1 + FEX 2610** captured run. No FPS or shader performance improvements are claimed from this incident.
