# Adreno 650 Turnip candidates versus DXVK 3.1.1 (research audit)

**Research date:** 2026-10-11. **Result:** No *verified correctly implemented* `storageBuffer8BitAccess` + complete DXVK 3.1.1 feature set was found for Adreno 650 in the inspected Mesa/Turnip sources or candidate release descriptions. This is **not proof that no private/custom binary exists**. No candidate binary was run on the user's S20+; the exact Mr. Purple T30 Turnip binary was not dumped. Preserve the functioning DXVK 2.7.1 control.

## Correct the Vulkan version distinction

[DXVK 3.x driver-support guidance](https://github.com/doitsujin/dxvk/wiki/Driver-support) (updated 2026-06-28) says a compatible driver **should support Vulkan 1.4**. But source at [`doitsujin/dxvk@v3.1.1/src/dxvk/dxvk_instance.h`](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/dxvk/dxvk_instance.h) explicitly sets `DxvkVulkanApiVersion = VK_API_VERSION_1_3`. DXVK 3.1.1 accepts Vulkan **1.3 minimum** if all its required 1.4-like features and extensions are present: simply increasing reported Vulkan version to 1.4 **neither provides nor proves the required features**. The device feature list is in [DXVK v3.1.1 `src/dxvk/dxvk_device_info.cpp`](https://github.com/doitsujin/dxvk/blob/v3.1.1/src/dxvk/dxvk_device_info.cpp), which specifies `ENABLE_FEATURE(vk12, storageBuffer8BitAccess, true)`.

Other mandatory checks include 256-byte push constants, `shaderInt8`, `storageBuffer16BitAccess`, `shaderInt64`, descriptor indexing/partially bound, `scalarBlockLayout`, `VK_EXT_depth_clip_enable`, `VK_EXT_robustness2` (`nullDescriptor`/`robustBufferAccess2`), `VK_KHR_maintenance5`, `VK_KHR_maintenance6`, `VK_KHR_load_store_op_none` and `VK_EXT_transform_feedback`. Some fields marked optional in the source are not release blockers. A successful 8-bit check is **necessary but not sufficient**.

## Source-level Mesa evidence (actual SD865 device profile)

- [Mesa 26.x source mirror `freedreno_devices.py`](https://chromium.googlesource.com/external/gitlab.freedesktop.org/mesa/mesa/+/25f7765d215e5b72adad2ab679df58d1d4959a16/src/freedreno/common/freedreno_devices.py): `GPUId(650)` inherits `a6xx_base, a6xx_gen3` around line 520; neither defines `storage_8bit=true`; `a7xx_base` defines `storage_8bit=true` around line 773. `a6xx_gen3` does enable **16-bit** storage, which is not equivalent.
- [Mesa Turnip `tu_device.cc` in a pinned 26.1.2 source tree](https://github.com/bmdhacks/armsx2-turnip/blob/armsx2/26.1.2/src/freedreno/vulkan/tu_device.cc): `features->storageBuffer8BitAccess = pdevice->info->props.storage_8bit` and `KHR_8bit_storage = device->info->props.storage_8bit`. The same source's A650 profile uses `a6xx_gen3`; newer A7xx base enables 8-bit. This also matches the [leegao wrapper Mesa tree](https://github.com/leegao/mesa-wrapper-CI/blob/gn_wrapper2/src/freedreno/vulkan/tu_device.cc), although its older field path is `a7xx.storage_8bit`.
- Mesa's [Freedreno documentation](https://docs.mesa3d.org/drivers/freedreno.html) still describes Turnip on Adreno 6xx as Vulkan 1.3. Hardware support, the reported Vulkan API version and actual shader correctness are different matters.

## Candidate driver / fork survey

| Build/fork | A650 support | 8-bit storage evidence | DXVK 3.1.1 status |
| --- | --- | --- | --- |
| Mesa Turnip 26.x reference / WN Turnip upstream-based | yes | A650 `storage_8bit` unset in official profile; newer Mesa and WN code use it as Vulkan feature gate | no source-backed complete compatibility |
| Mr. Purple T30 / PurpleVK wrapper on user's S20+ | yes, detected | Actual captured DXVK log: wrapper-facing `storageBuffer8BitAccess=false` | **CONFIRMED rejected on device** (DXVK 3.1.1) |
| ARM SX2 `bmdhacks/armsx2-turnip` 26.1.2 | yes | A650 `a6xx_gen3`, 8-bit disabled; only A7xx base enables | no confirmed compatibility |
| `whitebelyash/mesa-tu8` gen8 | yes in GPU definitions | A650 still gen3; `storage_8bit=true` only A7xx base | no confirmed compatibility |
| `Ghael-V/Turnip-Lemon-Ade` | source defines A650 | A650 gen3; fork is mainly A8xx, no verified A650 implementation | no confirmed compatibility |
| `WinNative-Emu/Drivers` Sept 2026 | supports A650; upstream-main-based | release/README patches cover device/WSI/GMEM but not new A650 8-bit shader implementation | no confirmed compatibility |
| `Tranquility6789/Turnip-A650-Patched-Drivers` | yes; 24.1 R18 | README disclaims Winlator compatibility and provides no 8-bit feature tests; targets emulator crash | not a useful DXVK 3.x candidate |
| `K11MCH1/AdrenoToolsDrivers` Turnip 24.1.0 R18 original/experimental | yes, A6xx builds | historical `KHR_8bit_storage` patch included in one build, but explicitly removed from the separate `a6xx` release due to rendering corruption; aimed to help A750 | may *advertise* 8-bit but explicitly unsafe/unverified for A650 |
| `Weab-chan/freedreno_turnip-CI` 24.1 experimental | A6xx | experimental MR 28254 described as “fix games a7xx break some a6xx” | not a supported A650 path |
| `NightHammer1000/TurnipMagisk` (archived 2026-08-19) | claims A650 Vulkan 1.4 | **Version-only patch:** `patches/enable-vk14-a6xx.patch` removes `chip >= 7` condition for `apiVersion` and does **not** add A650 `storage_8bit` or shader implementation | Vulkan version string may say 1.4, but **NOT proved compatible**; likely still missing storage8 and not conformant to Vulkan 1.4 |
| `jtiberius9-spec/vili-wrapper-build` | targeted A660 | wrapper **force-enables** storage bits, no A650 shader correctness evidence. Adreno 660 has distinct A6xx gen4 profile but inspected Mesa baseline does not enable storage8. | cannot generalize claimed startup success to A650 or full DXVK compatibility |

Relevant releases/docs: https://github.com/K11MCH1/AdrenoToolsDrivers/releases/tag/v24.1.0_R18 ; https://github.com/Weab-chan/freedreno_turnip-CI/releases ; https://github.com/NightHammer1000/TurnipMagisk/blob/main/patches/enable-vk14-a6xx.patch ; https://github.com/WinNative-Emu/Drivers ; https://github.com/jtiberius9-spec/vili-wrapper-build .

## Feature query protocol (critical to separate wrapper advertising from underlying driver)

On the same exact T30 build, capture:
1. Direct Turnip ICD `vkGetPhysicalDeviceProperties2().properties.apiVersion`.
2. Direct Turnip ICD `vkGetPhysicalDeviceFeatures2` with `VkPhysicalDeviceVulkan12Features`: `storageBuffer8BitAccess`, `uniformAndStorageBuffer8BitAccess`, `storagePushConstant8`, `shaderInt8` and Vulkan 1.1 16-bit, plus extension/limit list.
3. Same queries *through the PurpleVK wrapper*. The previously implemented opt-in overlay probe at `tools/ff7r_wrapper8bit_patch.py` logs direct vs wrapper values, and **never force-enables unsupported flags**. This is diagnostic-only and is not a tested WCP on the device.
4. If any fork reports `storageBuffer8BitAccess=true`, confirm `vkCreateDevice` with feature enabled and compile/execute a real SPIR-V shader using `StorageBuffer8BitAccess` via a dEQP-VK/conformance test; check output for correct 8-bit loads/stores, signedness, unaligned accesses, cross-word writes, and memory hazards. An advertised flag, instance version string or successful game menu is **not** a conformance result.
5. For a promising build, run the separate exhaustive `DXVK_SD865_DIAGNOSE=1` 3.x source audit to list **all** mandatory features, then full FFVII Remake rendering and cutscene checks. Only a confirmed Vulkan path, real shader correctness and a complete device-feature audit qualify as “3.1.1 compliant”.

Do **not** use `FD_DEV_FEATURES=storage_8bit=1`, wrappers force-setting `storageBuffer8BitAccess`, falsified Vulkan 1.4 reporting, or globally disabled DXVK feature checks as a substitute for implementation.

## Decision

- **No compatible ready-made A650 Turnip driver confirmed.**
- The historical R18 experimental patch and 2026 version-override Magisk build are **not reliable counterexamples**.
- Prioritize the user's working DXVK 2.7.1 branch plus selective A650-safe optimizations and FEX 2610 profiling.
- If explicit 3.x support is a long-term requirement, first implement/test true 8-bit SSBO storage semantics for A650 in Mesa/IR3 (potentially via compiler lowering), and only then validate all DXVK 3.1.1 requirements; do not spoof the GPU generation.
