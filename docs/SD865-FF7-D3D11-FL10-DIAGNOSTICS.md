# Diagnose FF7 Remake DX11 Feature Level 10 startup failure

## Evidence and intent

The Snapdragon 865 / Adreno 650 / Mr. Purple T30 setup is reported to boot
FF7 Remake on DXVK **2.7.1 and below**, while the experimental SD865 DXVK
**3.1.1** branch produces Unreal Engine's generic "DX11 feature level 10
is required" dialog. DXVK 3.1.1 also requires additional Vulkan
capabilities compared with 2.7.1.

The 3.1.1 source already rejects Vulkan adapters lacking required device
features. The original error log reports only the **first** failed feature,
which can be lost because GameNative's DXVKHelper sets DXVK_LOG_LEVEL=none.
This branch adds an opt-in full list of unsupported Vulkan requirements.
It does **not** bypass or spoof D3D11 FL10, Vulkan extensions, or shader
features and will not make an actually incompatible 3.1.1 driver run.

## Diagnostic setup in GameNative

Use an APK containing `Ragnarok93/GameNative` PR #51 or equivalent
logging fix; otherwise verify manually that the effective container
DXVK_LOG_LEVEL is not overridden to `none`.

Select the latest diagnostic WCP from the workflow artifact for
`feature/sd865-fl10-diagnostics-20261010`.
Configure the FF7 Remake container's **Environment** tab:

```env
GN_DXVK_DIAGNOSTICS=1
DXVK_SD865_DIAGNOSE=1
DXVK_LOG_LEVEL=info
```

Optional: set `DXVK_LOG_PATH` to an existing, writable path visible
to the Wine game. Do not use `DXVK_LOG_PATH=none`.

The failing 3.1.1 startup should emit `Found device:`, followed by
`Skipping: Device does not support required feature '...'`, plus the
new `DXVK-SD865 compatibility audit:` and `MISSING required Vulkan
feature: ...` lines. Copy the first 100-200 lines of the D3D11/DXGI
logs and all `DXVK-SD865 compatibility audit` lines.

If the audit is absent:
- Confirm `d3d11.dll` and `dxgi.dll` from the same diagnostic WCP
  are actually loaded by `FF7Remake_.exe` and D3D11 mode is selected.
- Check whether GameNative forced `DXVK_LOG_LEVEL=none` again.
- Check Wine Vulkan loader and `vkCreateInstance` failures before adapter
  filtering. No feature probe is possible if Vulkan never enumerates.
- Verify the selected physical GPU is Adreno 650 with Mr. Purple T30
  rather than a fallback or another ICD.

## Resolution gate

1. Compare with the same driver using the separately packaged
   DXVK 2.7.1 compatibility WCP; preserve the known working setup.
2. Diagnose missing Vulkan 3.1.1 requirements.
3. Only restore real functionality if the underlying driver exposes the
   missing required capability correctly. If capability is genuinely
   absent, DXVK 3.x requires a proper alternative implementation or
   driver fix; a D3D11 feature-level override is insufficient.
4. Avoid changing frame pacing/LSFG, async shaders, graphics driver
   and translation runtime during this regression isolation.

## First captured on-device evidence (2026-10-11)

The user supplied a 22-line DXGI log and a 938-line Wine log from the S20+.
**DXVK 3.1.1 really did load and attempt Vulkan adapter selection, but failed
before creating a rendering device**:

```text
DXVK: 3.1.1
Found device: Wrapper(PurpleVK-public Adreno (TM) 650 (git-62ac221a33)/unknown) (Wrapper driver 26.2.99)
Skipping: Device does not support required feature 'storageBuffer8BitAccess'
DXVK: No adapters found.
Failed to initialize DXVK.
```

Wine also recorded native `d3d11.dll` and `dxgi.dll`, plus `libarm64ecfex.dll`
in the FF7 game process. No `d3d12.dll`, successful D3D11/DXGI present,
`DXVK-SD865 compatibility audit:`, or `FEX-FF7R-PHASE0` marker was seen.
The Vulkan feature audit was not enabled or its marker was not captured in
these logs, so other missing features remain unknown.

**Action:** The *first identified incompatibility* is a reported Vulkan feature,
not a demonstrated D3D11 FL10 emulation bug. Compare raw Turnip
`VkPhysicalDeviceVulkan12Features.storageBuffer8BitAccess` against the
PurpleVK wrapper report. If underlying Turnip advertises support but PurpleVK
does not, fix wrapper propagation; if unsupported, investigate a compliant
driver/implementation. Never spoof the feature at DXVK level. A
[similar wrapper project](https://github.com/jtiberius9-spec/vili-wrapper-build)
reports the same symptom on Adreno 660, but that does not establish that our
wrapper has the identical defect. Vulkan 1.4 mandates 8-bit buffer storage,
while earlier Vulkan versions can have different requirements.

Use `DXVK_SD865_DIAGNOSE=1` with this branch's diagnostic WCP to enumerate
*all* missing requirements after the first blocker. Keep DXVK 2.7.1 for the
separate working-renderer performance baseline. No 3.1.1 success or FPS
improvement is established.
