# FF7 Remake — SD865 / Adreno 650 / Mr. Purple T30 prerelease

**Status: experimental prerelease, hardware verification pending.** This DXVK-SD865 3.1.1 build is prepared as a GameNative-installable `.wcp` containing Windows x86/x64 PE DLLs, **not** ARM64EC-native libraries.

**Driver target:** Mr. Purple T30 (26.3.0-devel), advertised Vulkan 1.4.359 and A6xx support. Driver advertisement does not guarantee that the selected GameNative Vulkan ICD exposes all DXVK 3.x required features.

## Changes

- On identified **Qualcomm Adreno 650 with Mesa Turnip**, for the exact executable `FF7Remake_.exe` (or `FF7Remake.exe`), an experimental **2-thread background shader compiler limit** is applied. This limits competition for the CPU while FEX translates the game; the performance effect remains unmeasured on this device.
- Explicit `dxvk.numCompilerThreads` and `dxvk.sd865CompilerThreads` settings take priority. Disable the FF7 tuning with `dxvk.sd865FF7RemakeTuning = False`.
- Logs expose the actual Turnip Vulkan `driverInfo` and D3D11-related Vulkan feature flags to diagnose Unreal Engine's `DX11 feature level 10 is required` error.
- No D3D feature levels, Vulkan features, descriptor support, render passes, or synchronization are spoofed or weakened.
- The packaged `.wcp` includes the GameNative `profile.json` and **explicit x32/x64 directory entries**, verified by packaging tests.

## Install in Ragnarok93/GameNative

1. Download this GitHub prerelease's **`.wcp` file directly** (or extract it from the GitHub Actions artifact ZIP, which is always a ZIP wrapper).
2. In GameNative: **Settings → Contents Manager → Import from device**; select the `.wcp` and verify its type is **DXVK**.
3. For the FF7 Remake game/container set **Graphics → DX Wrapper = DXVK**, select the imported `sd865-<sha>` DXVK version, and select **Mr. Purple T30** Turnip with **Use Adrenotools Turnip** enabled.
4. Make sure **FF7 Remake actually uses Direct3D 11**. It can run via **D3D12/VKD3D** despite `-dx11` / `-d3d11` launch arguments; in that case DXVK is not used and this package cannot change the renderer. Verify DXVK logs and `DXVK-SD865` markers before benchmarking.
5. For a first reproducible test, try **1152×648**, textures High, shadows Low, AA Low, AO Off. Disable LSFG and generated frames; target **30 real rendered FPS** and compare under the same FEX/Proton and driver settings.

## DXVK options

The game-specific two-worker tuning is automatic only for the A650 Turnip / matching FF7 executable combination, with no ordinary or SD865 worker-count override:

```ini
dxvk.sd865Profile = Auto
dxvk.sd865FF7RemakeTuning = True
dxvk.sd865Diagnostics = True
dxvk.sd865CompilerTelemetry = False
dxvk.sd865StatsInterval = 0
```

To override the two-worker experiment:

```ini
dxvk.sd865CompilerThreads = 3
```

To disable the automatic game-specific change entirely:

```ini
dxvk.sd865FF7RemakeTuning = False
dxvk.sd865CompilerThreads = 0
```

GameNative may override `DXVK_LOG_LEVEL` to `none`. For diagnostic collection, ensure the final environment sets `DXVK_LOG_LEVEL=info`, using the optional test hook in the [GameNative guide](https://github.com/Ragnarok93/dxvk-SD865/blob/feature/sd865-foundation-20261009/docs/SD865-GAMENATIVE-TESTING.md) if necessary.

## Troubleshoot FF7's DX11 feature-level error

The Unreal Engine error **does not prove missing D3D11 FL10 support**; it can also occur when Vulkan device creation fails. Capture startup DXVK logs including:

- `DXVK: 3.1.1`; `DXVK-SD865: GPU=...`; `driverInfo=...`; `Vulkan=...`
- `DXVK-SD865 FF7 Remake Vulkan D3D11 prerequisites: ...`
- `D3D11InternalCreateDevice: Maximum supported feature level: ...`, or any earlier Vulkan/driver error

If no D3D11 DXVK log exists and VKD3D is loaded, the game is not using this DLL package. Don't force `d3d11.maxFeatureLevel` to advertise unsupported features.

**On-device performance and correctness are unverified.** Please provide the startup log, 30fps and frametime results, and screenshots of visual anomalies to guide the next optimization pass.
