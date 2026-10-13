# FF7R backport validation — 2026-10-13

Source checkpoint: `340eb6ad710625f638975fcda617f18c88413d6d`.

- 49 tests pass, including a native-compiled display-refresh regression that produced SIGFPE on the baseline and passed after backporting both upstream fixes.
- x64 and x32 PE cross-compilation passes.
- GameNative WCP zstd integrity, profile.json and all x32/x64 DLL checks pass.
- CI: https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38347962972
- Artifact: ff7r-phase0-dxvk271-gamenative (ID 11788989089).
- Device feature checks, Vulkan API minimum and legacy DXBC compiler bytes are unchanged from `d82db60`.

Six additional upstream commits from the v3.1.1 ancestry are present: e11a953a, b1ef9e7c, 3c6a6ff1, 662b5068, 0aea8528 and 64542839. Prior tiler secondary-command-buffer backport is retained. This is a selective backport on 2.7.1, not wholesale DXVK 3.1.1 or an implementation of missing storage8 semantics.

Turnip counterpart: Ragnarok93/Banners-Turnip checkpoint f39c5f7, matched API29 A77 control/program-reference candidate on Mesa 76b9372. Both compiled and passed ABI/provenance checks in run 38348570456.

Remaining gate: FF7R startup, visuals, cutscenes/combat, stability and real-frame median/p95/p99 on the S20+. Build/test success does not establish speedup or Vulkan conformance. Keep LSFG/vkBasalt enabled in-container, LSFG FG disabled in-game, textures Low and other conditions fixed. Change DXVK first using the existing driver, then test both new Turnip profiles with the same accepted DXVK. Three matched warm-cache trials per arm.
