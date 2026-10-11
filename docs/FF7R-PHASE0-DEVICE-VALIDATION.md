# FF7 Remake Phase 0 — DXVK / FEX runtime attribution (2026-10-11)

**Implemented on this branch:** opt-in DXVK 2.7.1 D3D11 device-success marker in `src/d3d11/d3d11_main.cpp`, one-time DXGI successful-present marker in `src/dxgi/dxgi_swapchain.cpp`, streaming parser `tools/ff7r_phase0_report.py`, regression tests `tests/test_ff7r_phase0_report.py`, and isolated .wcp workflow `.github/workflows/ff7r-phase0-dxvk-wcp.yml`. No renderer/pacing/barrier/feature-level behavior was intentionally changed. No Android device benchmark or launch verification has occurred.

**FEX companion:** https://github.com/Ragnarok93/FEX/blob/feature/ff7r-sd865-architecture-20261011/docs/benchmarks/ff7r-phase0-diagnostics.md

## Source code cross-reference

- [upstream DXVK](https://github.com/doitsujin/dxvk) and the exact DXVK 2.7.1 release parent `c3dd74be6baec53786d4e064a572185b70347a17`: follow existing D3D11 device creation, DXGI swapchain and logging structure. This branch remains descended from 2.7.1; there is no 3.x requirement bypass.
- [DXVK-GPLALL/GPLAsync](https://github.com/Digger1955/dxvk-gplall), [Sporif/dxvk-async](https://github.com/Sporif/dxvk-async): compare later for pipeline-compilation scheduling and caching **only after Phase 0**. Their `DXVK_ASYNC`, `DXVK_GPLASYNCCACHE`, legacy state-cache and low-latency paths are fork-specific and **not presumed functional in our vanilla DXVK 2.7.1 baseline**. Async may temporarily omit rendering while compiling.
- [FEX upstream](https://github.com/FEX-Emu/FEX): preserve ARM64EC/WoW64 translator startup initialization, config loading and one-time process logging. This phase does not alter JIT semantics.
- [VKD3D-Proton](https://github.com/HansKristian-Work/vkd3d-proton): possible D3D12 rendering backend. The DXVK DXGI front end can present for a D3D12 command queue. That is *not* evidence that DXVK implements the D3D12 renderer.

## Build / installation

1. On this branch, open GitHub Actions **FF7R Phase-0 DXVK 2.7.1 diagnostic WCP**. On push the workflow builds/tests/uploads an archive; only a manually dispatched run may publish a prerelease. Check run status before importing.
2. The uniquely named `ff7r-phase0-dxvk271-<sha>.wcp` contains 32/64-bit PE DLLs and `profile.json`. This is a diagnostic WCP, **not** a faster version. Save your existing working DXVK WCP and GameNative container profile.
3. Install via GameNative Contents Manager; select it explicitly for FF7 Remake. Check the actual installed runtime DLLs and game executable path. Do **not** assume `-dx11` forces a D3D11 session.
4. Only for a diagnostic run, in the game's environment variables:
   ```text
   DXVK_FF7R_PHASE0=1
   FEX_FF7R_PHASE0=1
   GN_DXVK_DIAGNOSTICS=1
   DXVK_LOG_LEVEL=info
   ```
   `GN_DXVK_DIAGNOSTICS=1` only works when GameNative includes its existing opt-in DXVK logging change. Older GameNative builds may override `DXVK_LOG_LEVEL` to `none`; in that case collect effective Wine stdout/log output or use the newer build without editing the GameNative repository. Optionally use `DXVK_LOG_PATH` pointing to an existing *writable* path visible to Wine. `DXVK_HUD=api,version` is only supplementary.
5. Launch directly into one gameplay scene, wait for first successful present, then exit. Export the game-specific DXVK `*_d3d11.log` and `*_dxgi.log` plus any FEX/Wine logs from that **single** process/run. The DXVK logger routes through Wine's debug output when possible; enabling logging and capturing a file are separate prerequisites.
6. Disable instrumentation and verbose logging for performance measurements. Leave LSFG off until source-frame measurements can be verified.

**Expected diagnostic markers (only after code actually loads):**

```text
DXVK-FF7R-PHASE0: d3d11_device_created exe=FF7Remake_.exe feature_level=11_0
DXVK-FF7R-PHASE0: first_dxgi_present exe=FF7Remake_.exe d3d12_queue=0 sync_interval=0
FEX-FF7R-PHASE0: backend=ARM64EC app=FF7Remake_.exe pid=... wine=1
```

These are **examples of format**, not observed logs. If the DXGI marker reads `d3d12_queue=1`, the present came from a D3D12 command queue; D3D12 rendering belongs to VKD3D, even when the DXGI DLL comes from DXVK. A successful `d3d11_device_created` marker **without** a successful D3D11-type DXGI present does not establish the main rendering path. DXGI `Present` success does **not** prove display scan-out or source FPS.

Use the offline classifier (multiple paths allowed; don't merge logs across sessions):

```bash
python3 -m unittest discover -s tests -p test_ff7r_phase0_report.py -v
python3 tools/ff7r_phase0_report.py game_d3d11.log game_dxgi.log fex.log --json-out ff7r-phase0.json
python3 tools/ff7r_phase0_report.py game_d3d11.log game_dxgi.log --require-api d3d11
```

Output API evidence values:
- `d3d11_dxvk_present_path`: D3D11 device and DXGI present for non-D3D12 queue in this session. Does not prove displayed frame cadence.
- `d3d12_dxgi_present_path`: first DXGI present for a D3D12 command queue. Does **not** mean DXVK translates D3D12.
- `d3d11_device_only_no_present` / `dxgi_present_no_d3d11_device_evidence`: incomplete evidence.
- `mixed_or_ambiguous`: both DXGI present types (possibly multiple applications/runs); investigate.
- `unverified`: no qualified markers, not evidence of DXVK absence.

## Exit criteria

- DXVK diagnostic WCP compiles and builds correctly on CI (not yet asserted).
- Known-good 2.7.1 baseline still boots and renders; no controller, audio, cutscene, or visual regression.
- Distinct FEX code WCP identifies ARM64EC/WoW64 translator at startup.
- One single-game session produces matching API attribution and raw logs; user-supplied frame timing capture exists with LSFG off.
- A tested WCP can be immediately rolled back. Only then advance to DXVK/FEX hotspot profiling and experiments.

Current Phase-0 status: **source probes and workflow prepared; device evidence and build results pending**.
