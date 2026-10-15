# DXVK 2.7.1 → 3.1.1 selective backport ledger (FFVII Remake / Adreno 650)

Status: active review ledger for `feature/ff7r-adreno650-telemetry-20261014`. This is a selective compatibility audit, not a claim that the 3.1.1 source tree has been fully ported. The branch must remain based on upstream DXVK 2.7.1 and Vulkan 1.3; newer changes that require newer Vulkan features, changed shader interfaces, or unverified driver behavior are not accepted wholesale.

## Confirmed target and invariants

- Base release: upstream DXVK 2.7.1, `c3dd74be6baec53786d4e064a572185b70347a17`.
- Device/workload: Snapdragon 865 / Adreno 650, GameNative WCP, FFVII Remake D3D11 path only after logs confirm that DXVK is actually active.
- Deliverables: x86 and x64 GameNative `.wcp`; no Windows installer or standalone Windows release.
- Required compatibility: Vulkan 1.3, original resource-lifetime and synchronization guarantees, shader/pipeline correctness, FEX/Wine interoperability.
- Evidence standard: source review and automated build/tests are not device-performance evidence. Keep each candidate independently reversible and compare matched, warmed/cold-cache trials.

## Candidate ledger

| Upstream change | Disposition | Reason / validation needed |
|---|---|---|
| `d92226b6a9e5ac7d9e9f00999b0feb54c9e1987e` — use secondary command buffers for all render passes on tilers | **Already backported** in `src/dxvk/dxvk_context.cpp` | Uses the existing `preferRenderPassOps` capability hint. Needs S20+ Turnip correctness and frame-pacing A/B; secondary recording can add CPU overhead on trivial passes. |
| `bc94fe40b59fb46efd27223f3f32856eebc3eb99` — precompute push-data gather copies | **Selected for backport** | Replaces per-draw bit-mask walking with a layout-time compact copy plan. The implementation must preserve the 2.7.1 layout and resource/constant offsets, and retain the direct resource-only fast path. Verify x86/x64 WCP builds and shader/render correctness. |
| `660d382288` — cap shader compiler workers at eight on 32-bit hosts | **Selected for a small compatibility backport** | Bounds address-space pressure on 32-bit processes. Preserve explicit `DXVK_FF7R_COMPILER_THREADS` override behavior and do not change the 64-bit default. Validate both WCP architectures. |
| `a137f78453` / `c96835baa0` — make legacy descriptor update templates configurable, disabled by default upstream | **Not blindly backported** | The current branch already has a batched legacy descriptor-write path and its own 32-bit considerations. Upstream explicitly reverted the default-on behavior for environments where templates fail or regress; any change needs device-specific A/B and compatibility tests. |
| `398c950926` — remove unused push-data members in shader IR | **Deferred** | Changes shader IR and push-constant layout generation, with correctness risk beyond the narrow CPU gather optimization. Requires shader corpus and visual validation before adoption. |
| `b42d23cfa0` — fix unsynchronized render-pass reversion condition | **Needs explicit source-context review** | Synchronization correctness fix, not a speculative performance toggle. Compare the exact 2.7.1 hunk and test hazard behavior before changing. |
| `788b37e1bf` — shader-cache writer wakeup/queue behavior | **Not backported** | Changes background thread shutdown and DLL-unload behavior; this is a lifecycle fix with broad concurrency implications, not a local FF7R optimization. |
| `84c34155aa` — adjust legacy descriptor pool allocation | **Not backported yet** | Changes descriptor capacity and pool accounting. Do not transplant without checking the 2.7.1 allocator's inline-uniform support and target driver's limits. |
| `bc0b93c999`, `351b40fea9`, `3379a21d60` and related descriptor-heap/spec-data commits | **Deferred as a group** | Descriptor heap/spec-constant fallback work is a multi-commit feature family. Cherry-picking isolated pieces risks incomplete layouts and Vulkan feature assumptions. |
| DXVK 3.1.1-wide changes outside the reviewed commit window | **Not yet audited** | The upstream comparison spans hundreds of commits; the GitHub compare endpoint exposes a limited page. This ledger intentionally does not claim every intervening commit has been reviewed. Continue by subsystem and record exact source commits before backporting. |

## Next implementation/verification gates

1. Land the push-data gather optimization as one source checkpoint.
2. Land the 32-bit worker cap separately, preserving the existing explicit override.
3. Run telemetry-tool tests, attribution tests, x86/x64 cross-compilation and WCP packaging for each integrated source checkpoint.
4. Inspect the exact unsynchronized-render-pass fix against this branch before deciding whether it applies.
5. Use matched Adreno 650 captures to decide whether the tiler render-area backport, push-data gather, lookup victim slots, and duplicate-bind suppression are retained. Do not report a speedup without real device results.
