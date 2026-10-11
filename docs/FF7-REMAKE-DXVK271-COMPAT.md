# FF7 Remake SD865: DXVK 2.7.1 compatibility package

This prerelease is a GameNative `.wcp` packaged from **upstream DXVK 2.7.1**
(commit `c3dd74be6baec53786d4e064a572185b70347a17`), with no changes
to DXVK's D3D11 feature-level checks, Vulkan shader compiler or renderer.
It is not the newer DXVK 3.1.1-SD865 source, and does not claim DXVK 3.1.1
compatibility. Both 32-bit and 64-bit PE DLLs are included, as GameNative
expects. The profile has a unique `sd865-271-compat-...` version name.

## Why this exists

On Galaxy S20+ / Snapdragon 865 / Turnip Mr. Purple T30, the user reports
that DXVK 2.7.1 boots and renders `FF7Remake_.exe`, while DXVK 3.1.1
produces the game's generic DX11 Feature Level 10 error. The newer
version has additional Vulkan requirements. Without a log showing the
first incompatible feature or failed Vulkan call, do not disable the
required-feature checks or spoof feature levels.

This WCP is a separately installable baseline for repeatable comparisons.
It is **not** tested on the device by GitHub CI and is not yet benchmarked.

## Installation and comparison

1. Back up the existing GameNative game/container configuration.
2. Import this `.wcp` through GameNative's Contents Manager.
3. Select DXVK and the `sd865-271-compat-...` package for FF7 Remake.
4. Keep Wine/Proton, FEX, Mr. Purple T30 Turnip, VKD3D and FF7 game
   settings unchanged versus the known-working DXVK 2.7.1 installation.
5. Confirm the game actually chooses Direct3D 11; verify the DXVK log/HUD.
6. Verify that startup, gameplay, cutscenes, effects, and combat all work.
   Disable LSFG/frame generation when capturing actual frame times.
7. Repeat with the DXVK 3.1.1 experimental WCP **with startup diagnostics
   enabled**, and capture the first device rejection reason.

For a low-overhead CPU contention experiment, test DXVK's existing
`dxvk.numCompilerThreads = 2` option in `dxvk.conf` on 2.7.1; compare
against its normal automatic/default thread scheduling. No compiler
thread limit is applied by default in this baseline.

**Do not** apply `d3d11.maxFeatureLevel` overrides to bypass missing Vulkan
support. If the 2.7.1 WCP also fails while an older 2.7.1 install works,
first validate GameNative DLL loading, WCP path/layout, Wine selection
and actual DXVK log markers. That would point to a packaging/loader
difference rather than proving a 2.7.1 graphics regression.

## Reproducibility / provenance

- FEX/DXVK/GameNative/Wine versions and hashes should be recorded.
- Only the PE DLLs and `profile.json` are packaged in the `.wcp`.
- Tar directory records are explicit to satisfy GameNative extraction.
- The GitHub Actions build must pass 32/64-bit build and package tests.
