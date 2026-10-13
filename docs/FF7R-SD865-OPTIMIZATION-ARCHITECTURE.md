# FFVII Remake Intergrade / SD865 — DXVK-specific optimization architecture

**Status (2026-10-12):** first DXVK optimization experiment is in this branch; device performance remains unverified.

**Current experiment:** upstream DXVK tiler render-area trimming backport is recorded in [`FF7R-DXVK-TILER-SECONDARY-CMD-BACKPORT.md`](FF7R-DXVK-TILER-SECONDARY-CMD-BACKPORT.md). It remains unverified on the S20+ and is not a performance claim.

**Primary cross-repository specification:** https://github.com/Ragnarok93/GameNative/blob/feature/ff7r-sd865-architecture-20261011/docs/ff7r-sd865/ARCHITECTURE.md

**Source branch:** `compat/ff7remake-dxvk271-sd865-20261010` at `5c9d3a04b281`, derived from exact upstream DXVK 2.7.1 release commit `c3dd74be6baec53786d4e064a572185b70347a17`. Existing `docs/FF7-REMAKE-DXVK271-COMPAT.md`, `.github/workflows/compat-dxvk271-wcp.yml`, `tools/package_gamenative_wcp.py`, and `tests/test_gamenative_wcp.py` are the packaging/control baselines.

## The gating question

FFVII Remake may use **D3D12/VKD3D instead of D3D11/DXVK** in GameNative despite `-dx11` / `-d3d11`. DXVK optimization results require D3D11-confirmed DLL/renderer logs (`d3d11.dll`, `dxgi.dll`, `DXVK_HUD=api,version` or logs), driver identity, actual game executable, shader cache and current configuration. D3D12-confirmed experiments belong in VKD3D. Do not run an FPS experiment on an unverified API.

## Reproducible branches and packages

1. Keep immutable DXVK 2.7.1 control WCP with x32/x64 D3D11 and DXGI binaries. Pin hashes of the PE DLLs, `profile.json` and input source.
2. Introduce any proposed speedup as a separate *named experimental WCP*, one code change per build, never overwrite a working compatibility WCP.
3. Keep the current standalone 3.1.1 diagnostic investigation outside this branch: https://github.com/Ragnarok93/dxvk-SD865/blob/feature/sd865-fl10-diagnostics-20261010/docs/SD865-FF7-D3D11-FL10-DIAGNOSTICS.md. Feature level 10 dialog is not sufficient evidence of which Vulkan capability failed. Never bypass mandatory features or spoof D3D feature levels.
4. Use GameNative branch with opt-in `GN_DXVK_DIAGNOSTICS=1` for start-up logs; disable verbose diagnostics during frame-time A/B.

## Investigation order (trace-guided, not blind toggles)

| Priority | Target | Evidence needed | Safe experiment | Reject on |
| --- | --- | --- | --- | --- |
| 0 | First-use shader/pipeline stalls | `DXVK_HUD=compiler,pipelines,frametimes`, cache state | `dxvk.numCompilerThreads=2` vs automatic; warmed/cold separate | longer compile/loading stalls, contention |
| 1 | D3D11 context, submits, synchronization | CPU profiles and Vulkan timing, draw/submit counts | Reduce demonstrably redundant submits/flushes with hazard tests | wrong resource state, missing frames, deadlocks |
| 2 | Upload/staging and memory | buffer/image churn, VRAM budget, peak RSS, texture streaming | Bound staging/allocation pools based on real lifetimes | pop-in, evictions, visual corruption, OOM |
| 3 | Descriptors/pipeline state churn | per-frame rebind/create rate | Cache bounded repeated state on verified lifetime | stale descriptors, incorrect materials |
| 4 | T30-specific Vulkan cost | actual device feature enumeration and render pass timing | Capability-gated alternative implementations | required feature absent, invalid sync |
| 5 | Present cadence | real display presents, Vulkan queue/present time | Only validated scheduling optimizations | stalling, repeated suboptimal swapchain, stale image |

Inspect `src/d3d11`, `src/dxvk` (context, queue, pipelines, barriers, memory), and `src/dxgi` only after profiles point to those areas; no assumptions from generic benchmarks. Do not inject driver-dependent features globally. Keep DXVK async forks, GPL async switches, and bypasses off unless their source and actual driver support are verified.

## Invariants / acceptance

- **Correctness:** original game scene outputs, transparency, texture residency, shaders, FEX/Wine interop, Vulkan synchronization, saves and cutscenes.
- **Measurement:** fixed scene/same warmed shader cache, identical 720p output and active DRS percentage (68–100%, ~490–720p), LSFG off; 3+ trials with raw real-frame duration or confirmed present timestamps.
- **Release:** verified .wcp layout, install + rollback, SHA256 and versioned manifest; 32/64-bit CI and on-device smoke/thermal/stutter tests. Publishing packages is a later phase.
- **Stop:** change in API, unresolved D3D11 FL10, missing Vulkan device capability, black textures, invalid rendering, >50ms hitch regression, memory runaway.

The tiler render-area experiment is the first DXVK source patch on this branch; it needs 32/64-bit CI and matched on-device A/B results before it can be retained as an optimization. Runtime graphics acceleration via VKD3D is outside the DXVK-specific track.
