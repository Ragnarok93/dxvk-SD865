# DXVK 2.7.1 → 3.1.1 selective backport ledger (FFVII Remake / Adreno 650)

Status: active review ledger for the unified working branch `feature/ff7r-adreno650-telemetry-20261014`. This is a selective compatibility audit, not a claim that the 3.1.1 source tree has been fully ported. The branch must remain based on upstream DXVK 2.7.1 and Vulkan 1.3; newer changes that require newer Vulkan features, changed shader interfaces, or unverified driver behavior are not accepted wholesale.

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
| `bc94fe40b59fb46efd27223f3f32856eebc3eb99` — precompute push-data gather copies | **Implemented in `262491a`, safety/compatibility follow-ups in `131fd15` and `0e8136f`** | Replaces per-draw bit-mask walking with a layout-time compact copy plan; retains the direct resource-only path. Byte-based copy arithmetic avoids alignment/aliasing assumptions. The first build exposed that the 2.7.1 `small_vector` lacks range iterators; indexed iteration fixes that. The corrected source passed x86/x64 cross-compilation and GameNative WCP packaging on commit `0e8136f` (workflow run [38668047612](https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38668047612)). Device correctness/performance remains unverified. |
| `660d382288` — cap shader compiler workers at eight on 32-bit hosts | **Implemented in `c8913b4`** | Bounds address-space pressure on 32-bit processes. The cap is applied before explicit config/FF7R override handling, so existing override behavior is preserved; 64-bit defaults are unchanged. x86/x64 cross-compilation and WCP packaging passed on commit `0e8136f` (workflow run [38668047612](https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38668047612)). |
| `a137f78453` / `c96835baa0` — make legacy descriptor update templates configurable, disabled by default upstream | **Not blindly backported** | The current branch already has a batched legacy descriptor-write path and its own 32-bit considerations. Upstream explicitly reverted the default-on behavior for environments where templates fail or regress; any change needs device-specific A/B and compatibility tests. |
| `398c950926` — remove unused push-data members in shader IR | **Deferred** | Changes shader IR and push-constant layout generation, with correctness risk beyond the narrow CPU gather optimization. Requires shader corpus and visual validation before adoption. |
| `b42d23cfa0` — fix unsynchronized render-pass reversion condition | **Not applicable to the current 2.7.1 source path** | The upstream hunk references `m_unsynchronizedDrawCount` / `MaxUnsynchronizedDraws`, which are absent from this branch's context implementation. No equivalent hunk exists to transplant. Revisit only if the relevant unsynchronized-render-pass implementation is separately backported. |
| `788b37e1bf` — shader-cache writer wakeup/queue behavior | **Not backported** | Changes background thread shutdown and DLL-unload behavior; this is a lifecycle fix with broad concurrency implications, not a local FF7R optimization. |
| `84c34155aa` — adjust legacy descriptor pool allocation | **Not backported yet** | Changes descriptor capacity and pool accounting. Do not transplant without checking the 2.7.1 allocator's inline-uniform support and target driver's limits. |
| `bc0b93c999`, `351b40fea9`, `3379a21d60` and related descriptor-heap/spec-data commits | **Deferred as a group** | Descriptor heap/spec-constant fallback work is a multi-commit feature family. Cherry-picking isolated pieces risks incomplete layouts and Vulkan feature assumptions. |
| `e40ba5f8b8`, `7f0c71c2e7`, `9138d7cdf9` — hash-indexed pipeline variant table | **Deferred pending scan telemetry** | Replaces a linear variant list with a concurrent adaptive table and changes graphics/compute instance ownership. The graphics path also has an FF7R last-instance cache and sampled scan-count telemetry. Use captures to show that variant scans are material before accepting this wider concurrency/memory change. |
| `c276b56bb8` — ignore some explicit D3D11 flushes on tilers | **Rejected for this workload** | The upstream commit itself warns of possible deadlocks and is a Unity-specific heuristic. Do not suppress FFVII Remake flushes without a reproducible correctness case and hazard analysis. |
| `bd20ebe959` — use persistent shader cache for DXBC-to-SPIR-V shaders | **Deferred as a dependency group** | Requires the DXVK cached-shader API and shader-cache infrastructure commits; this is a multi-commit startup/first-use behavior change. Audit the existing 2.7.1 cache path and cache-key/lifetime contract before transplanting. |
| `e3d3f69fe3` — reroute mapped allocations to cached memory on tilers | **Deferred pending memory traces** | Alters allocator behavior and can affect staging bandwidth, cache coherency, memory pressure, and resource lifetime. Needs device-specific mapped/upload measurements and memory-pressure tests. |
| `bd4395a9211fa6eb171d5a08a08d4033612fbfa1` — disable raster-related dynamic state when rasterizer discard is active | **Implemented; WCP CI passed, device validation pending** | Adds a dedicated dynamic-viewport context flag, omits viewport/scissor and other raster-related dynamic-state declarations for discard pipelines, and gates corresponding context command emission. Adapted to this fork rather than cherry-picked wholesale. WCP CI passed on `7764af18b03e1ac068f065d2d4f0fcf43eb3a9b2` (run [38879612618](https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38879612618)), including source-contract checks, x86/x64 cross-compilation, WCP packaging and artifact upload. Discard↔normal transition behavior and visual correctness on Adreno 650 remain unverified. |
| `7926853af7f3e9a05e9e9c94928a85cbada6b501` — omit unnecessary state for rasterizer-discard optimized pipelines | **Implemented; WCP CI passed, device validation pending** | Reuses the fork's existing `HasRasterizerDiscard` flag; does not add Vulkan requirements or import the separate geometry-shader `ExportsPosition` behavior. WCP CI passed on `7764af18b03e1ac068f065d2d4f0fcf43eb3a9b2` (run [38879612618]), including source-contract checks, x86/x64 cross-compilation, WCP packaging and artifact upload. Discard↔normal transition behavior and visual correctness on Adreno 650 remain unverified; no performance gain claimed. |
| DXVK 3.1.1-wide changes outside the reviewed commit window | **Not yet audited** | The upstream comparison spans hundreds of commits; the GitHub compare endpoint exposes a limited page. This ledger intentionally does not claim every intervening commit has been reviewed. Continue by subsystem and record exact source commits before backporting. |

## Next implementation/verification gates

1. Current verified gates: telemetry-tool tests passed at `0d8737f9f4b07254e6bf99d22ad3374d6d58c536` in [run #38880814788](https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38880814788); x86/x64 cross-compilation and WCP packaging passed at `7764af18b03e1ac068f065d2d4f0fcf43eb3a9b2` in [run #38879612618](https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38879612618). The exact documentation-follow-up head still needs its own WCP run to complete before claiming packaging is verified for that SHA.
2. Use matched Adreno 650 captures to decide whether the tiler render-area backport, push-data gather, lookup victim slots, and duplicate-bind suppression are retained. Do not report a speedup without real device results.
3. Use the `DXVK-FF7R-LOOKUP` scan count to decide whether the pipeline-variant table is worth the added complexity.
4. WCP CI passed for the rasterizer-discard pipeline and dynamic-state reductions on `7764af18b03e1ac068f065d2d4f0fcf43eb3a9b2` (run [38879612618]). Next gate: test discard↔normal pipeline transitions and visual correctness on Adreno 650 before matched device A/B testing.
5. Keep flush suppression, allocator policy changes, and persistent shader-cache backports deferred until their workload-specific contracts are verified.


## Additional upstream triage (2026-10-16)
- Reviewed upstream DXVK commit [`5cbf10835ec21e23d6aaeccfa4cffc5630276dc4`](https://github.com/doitsujin/dxvk/commit/5cbf10835ec21e23d6aaeccfa4cffc5630276dc4), which adjusts dual-source blending when a fragment shader does not export a second color output. This is primarily a correctness/compatibility fix, not a demonstrated FFVII Remake CPU optimization; it also changes render-target iteration and blend-factor normalization. Do not import it as an optimization without confirming the relevant shader-output metadata and blend-factor helper contracts in this 2.7.1 fork.
- No additional source optimization was applied in this pass: rasterizer-discard runtime correctness remains the active validation gate, and the deferred pipeline-table/allocator changes lack workload evidence. Keep Vulkan 1.3 compatibility and WCP-only packaging.
## Continued upstream audit (2026-10-16, shader-cache and descriptor-pool contract review)

- **Persistent DXBC-to-SPIR-V shader cache (bd20ebe959527cfa9bf59363caa125cb65230ecb) — still deferred; cache API must be ported as a dependency group.** The upstream D3D11 call site delegates shader construction to DxvkDevice::createCachedShader, keyed by ShaderKey.toString(). The 2.7.1 fork instead constructs D3D11CommonShader locally; this constructor also handles DXBC/SPIR-V dumps, immediate-constant-buffer (ICB) allocation/upload, shader registration, and binding-mask extraction. A correct backport must preserve those side effects on both cache hits and misses, prove that the key includes every translation-affecting input, and define cache lifetime/invalidation. Porting only the call-site hunk would be incomplete. No source changes made.
- **Descriptor-pool sizing (84c34155aa) — not a direct patch candidate for this fork.** The upstream patch adjusts an eight-type pool including inline uniform blocks and storage/texel descriptors. The 2.7.1 fork's DxvkDescriptorPoolSet::createVulkanDescriptorPool uses a six-type pool and a different m_maxSets/pool reuse model; the hunk does not apply as-is. The target's storage image and storage texel-buffer capacities are currently m_maxSets / 64; increasing them may be worth evaluating only if logs show descriptor exhaustion or allocation churn, but it is not a demonstrated fix for the observed Vulkan device-memory OOM. Do not copy the newer constants without a descriptor-demand and memory-cost audit.
- **Layered-rendering pipeline tracking (1d1d5cecd1f46e7de8fcacda72078c9caabe1fe5) — Vulkan-1.3-era candidate, low priority pending use-case evidence.** It separates layer and viewport shader metadata and marks pipelines that export a layer. This is pipeline/shader metadata plumbing rather than an obvious FFVII Remake hot-path win. It changes shader IR metadata and graphics-pipeline flags, so only revisit if the current 2.7.1 path has a relevant layered-rendering correctness/performance issue or a downstream optimization consumes the new flag.
- **Current disposition:** no source optimization was imported during this audit. The safest next implementation target remains the pipeline-variant table only if lookup telemetry shows meaningful linear scans; persistent shader caching requires a broader dependency/side-effect audit first. Maintain the single unified branch, Vulkan 1.3 target, and WCP-only x86/x64 validation.

## Pipeline-variant table dependency audit (2026-10-16)

- Verified the exact upstream commits: [`0d1304c732b038fb1cc2510c17e2502cf1a51898`](https://github.com/doitsujin/dxvk/commit/0d1304c732b038fb1cc2510c17e2502cf1a51898) adds `hash()` and `eq()` to graphics/compute pipeline state; [`7f0c71c2e7dc10016c1050298eeb50cf096b7d67`](https://github.com/doitsujin/dxvk/commit/7f0c71c2e7dc10016c1050298eeb50cf096b7d67) switches the graphics pipeline instance list to `DxvkPipelineVariantTable`.
- The 2.7.1 target still uses `operator==`/bytewise state comparison and `sync::List<DxvkGraphicsPipelineInstance>`; the exact state `hash()`/named `eq()` prerequisite is not present in `src/dxvk/dxvk_graphics_state.h`. Therefore, this is a dependency chain, not a one-file container replacement.
- The table change removes the state object from each instance and changes creation, lookup, and lifetime iteration. Existing callers retain instance pointers after `getPipelineHandle` releases `m_mutex`, while compilation state and Vulkan handles are updated atomically. A generic `std::unordered_map` replacement is not a safe substitute without proving pointer stability, concurrent lookup/insert behavior, and destruction/lifetime semantics.
- The state hash in the upstream prerequisite hashes the full state object's bytes with FNV-1a, matching its bytewise equality contract. Before importing it, verify that all compared bytes—including padding—are initialized deterministically in this fork and that the hash/equality invariants hold for every state constructor/copy path.
- **Disposition remains gated on device telemetry.** Existing `DXVK-FF7R-LOOKUP` samples report mean/max scanned entries and cache-hit percentage every 256 lookups (when `DXVK_FF7R_METRICS=1`). The last-hit cache already bypasses scans for repeated identical states. Until a current capture shows substantial scan lengths or sampled lookup cost, the added table's memory and concurrency complexity is not justified. If warranted, port the complete table dependency chain on the unified branch and validate both graphics and compute paths, not just graphics.
- No source optimization was imported in this audit. Vulkan 1.3 compatibility and GameNative x86/x64 WCP packaging remain mandatory.

## First-use MSAA resolve storage optimization (2026-10-16)

- Backported the focused logic from upstream [`f20f363191c019cbf0d792e4e8f660d46ebecb6c`](https://github.com/doitsujin/dxvk/commit/f20f363191c019cbf0d792e4e8f660d46ebecb6c) into `src/dxvk/dxvk_context.cpp`.
- The old path tested whether the destination was already write-tracked before enabling graphics-store tracking. If graphics stores had not yet been tracked, it could leave `needsNewBackingStorage` true and relocate the resolve destination on first use. The new path enables tracking first when needed, then rechecks the current tracking state; it retains the existing slow-path resource-access checks when graphics stores are already tracked.
- Expected benefit is avoiding an unnecessary first-use backing-storage replacement for eligible resolve destinations, reducing allocation/copy/descriptor invalidation work and potentially lowering transient memory pressure. This is a source-level hypothesis, not a measured FFVII Remake gain; it does not change allocator policy.
- Compatibility scope is the existing Vulkan 1.3 render-pass resolve path. No new Vulkan feature is required. Main risk is incorrect resolve destination preservation if tracking semantics differ in this older fork, so runtime validation must exercise first-use resolves, destinations previously sampled/written in the same render pass, MSAA color and depth/stencil resolves, and partial/subresource cases.
- Candidate `952cad8f306b43903c1fc177685baa951a52d7b5` (small-vector dynamic-state cleanup) was inspected but not imported: the target's corresponding dynamic-state arrays are already sized for the state sets it builds, so upstream's container change does not establish a benefit here.
- Validation status: awaiting fresh x86/x64 GameNative WCP build and source-contract workflow for the source commit, followed by device correctness/performance testing. Keep PR #4 unmerged until validation is complete.

## Immediate constant-buffer transfer-stage tracking fix (2026-10-16)

- Adapted upstream [`a16e14d791c632828325f08b6bf4fed22afb3f3b`](https://github.com/doitsujin/dxvk/commit/a16e14d791c632828325f08b6bf4fed22afb3f3b) to this fork's Vulkan 1.3-era synchronization API in `src/d3d11/d3d11_shader.cpp`.
- The ICB buffer already declares `VK_BUFFER_USAGE_TRANSFER_SRC_BIT`, `VK_BUFFER_USAGE_TRANSFER_DST_BIT`, and transfer read/write access, but its stage mask only included the shader stage. Adding `VK_PIPELINE_STAGE_TRANSFER_BIT` makes the declared transfer operations visible to DXVK's buffer synchronization tracking. This is a correctness/validation fix rather than a claimed frame-time optimization.
- Upstream reports this change fixes a validation error. This target's exact runtime manifestation is not yet confirmed; validation layers and device testing should verify upload, transfer, defragmentation/copy, and subsequent uniform reads.
- This uses the legacy Vulkan 1.0-compatible pipeline-stage enum already used by the fork and does not require Vulkan 1.4 or synchronization2.
- Build and source-contract validation are queued by the unified-branch commit. Do not treat it as runtime-verified until a fresh x86/x64 WCP build and device validation are complete.


## Failed image-relocation guards (2026-10-16)

- Adapted three focused upstream guards: [`28a321141951003782c60d1846122df35aaf5b8a`](https://github.com/doitsujin/dxvk/commit/28a321141951003782c60d1846122df35aaf5b8a) for D3D11 ClearUAV, [`fe8a4b5799032a4568776c8b56c452e574b51f65`](https://github.com/doitsujin/dxvk/commit/fe8a4b5799032a4568776c8b56c452e574b51f65) for video input/output, and [`5502fe6a83e0dcffdf7d747ba7d97b41c318d211`](https://github.com/doitsujin/dxvk/commit/5502fe6a83e0dcffdf7d747ba7d97b41c318d211) for shader-based image-to-buffer readback.
- These paths previously ignored the boolean result from `ensureImageCompatibility` and continued with the operation even if the image could not be made compatible. They now log an error and return from the queued operation on failure.
- Relevance: hardens failure behavior under allocation/relocation pressure, including cases that can lead to invalid follow-on work after an allocation failure. This does not recover memory, prevent the original OOM, or claim a performance improvement.
- Scope is deliberately limited to these three call sites. Other `ensureImageCompatibility` uses have different fallback contracts and were not changed.
- Validation required: x86/x64 GameNative WCP CI; on-device pressure testing for ClearUAV and readback; video path smoke test where available; verify logs fail cleanly rather than issuing subsequent operations. Vulkan 1.3 API baseline unchanged.


## Feedback-loop clear fusion guard and memory-property fallback (2026-10-16)

- Backported the focused guard from [upstream `843b200443e7c76215aefe6594937ddd0f0bd178`](https://github.com/doitsujin/dxvk/commit/843b200443e7c76215aefe6594937ddd0f0bd178): deferred clears are no longer fused into a render pass when their image aspects overlap the active feedback-loop aspects. This preserves the required clear/read ordering and avoids incorrect rendering. Vulkan 1.3 baseline unchanged; validate feedback-loop rendering and normal clear batching.
- Backported the uncommon memory-property fallback from [upstream `a7841308f0394b9c5dd6800a62f3079b7a2e8573`](https://github.com/doitsujin/dxvk/commit/a7841308f0394b9c5dd6800a62f3079b7a2e8573). The previous 16-entry property-mask lookup wrapped uncommon property flags modulo 16, which could return a mask for unrelated flags. The new path scans actual memory types when the requested property bitmask is outside the precomputed table and preserves the prior fallback only if no matching type exists.
- This improves allocator correctness for uncommon memory-property combinations, but is not claimed to reduce the previously observed OOM events by itself. Validate standard host-visible/coherent/cached requests and any uncommon extension property combinations on target hardware.
- Both changes are scoped to existing code paths and do not require Vulkan 1.4 or synchronization2. x86/x64 WCP CI and device-side correctness validation remain required.


## Transform-feedback synchronization and render-pass preservation (2026-10-16)

- Adapted upstream [`a54af5db88ea66fae1469a99cfcc30150f413f9c`](https://github.com/doitsujin/dxvk/commit/a54af5db88ea66fae1469a99cfcc30150f413f9c): when graphics pipeline state or specialization constants may require a rebind during active transform feedback, pause transform feedback and mark its buffers dirty rather than immediately spilling the render pass. Existing hazard checks can then decide whether a barrier and pass spill are actually needed.
- Also use the configured transform-feedback counter slices for hazard checks, rather than only the active counter slices. Pausing transform feedback clears the active slices; checking the configured counters preserves counter hazard tracking across that pause.
- Expected upside: avoid unnecessary render-pass interruptions for transform-feedback workloads. This is workload-dependent and not a claimed FFVII Remake performance win. Requires CI and device validation for transform-feedback pause/resume, counter reuse, pipeline/spec-constant changes, and actual hazard cases. Vulkan 1.3 baseline unchanged.


## Dual-source blending with a missing second fragment output (2026-10-16)

- Adapted upstream [`5cbf10835ec21e23d6aaeccfa4cffc5630276dc4`](https://github.com/doitsujin/dxvk/commit/5cbf10835ec21e23d6aaeccfa4cffc5630276dc4).
- Dual-source blending now limits color attachments to render target 0 without masking the fragment shader output mask. If the shader does not export the second output, any dual-source blend factors are replaced with `VK_BLEND_FACTOR_ZERO` before pipeline creation.
- This avoids constructing a pipeline with dual-source factors that reference a nonexistent second fragment output. It is a correctness/compatibility fix, not a claimed performance improvement.
- The target already provides `util::isDualSourceBlendFactor`; no new helper or Vulkan feature is required. Vulkan 1.3 baseline unchanged.
- Validate with dual-source blend factors when the shader exports both outputs, when it exports only one output, and when blending is disabled; also verify normal multi-render-target output remains unchanged. WCP build and source-contract tests are required, followed by a device/game smoke test if the workload exercises this path.

## Latest FFVII Remake allocation/queue capture review (2026-10-16)

Source: committed companion log `logs/ff7remake__d3d11.txt` at branch head `039a6779b0bfdc0bed922d7dcd66356ce8b9529d`. This is runtime evidence from one capture, not a matched before/after performance trial.

- **Actual driver allocation failures persist.** Five `stage=driver_retry` events are visible in this log; each reports `first_vkresult=-2` and `retry_vkresult=-2` (`VK_ERROR_OUT_OF_DEVICE_MEMORY`) with `recovered=0`. Requests are three 256-MiB attempts and two 128-MiB attempts. Across the event snapshots, DXVK tracked allocated memory is 3.32, 3.44, and 3.57 GiB; tracked used memory is 3.02, 3.11, and 3.24 GiB. Driver-reported allocated memory is 3.08, 3.09, and 3.22 GiB, respectively. Values are converted from the raw byte fields using GiB (2^30 bytes).
- The allocator's **per-failure reclaim pass frees 0 bytes** and reports zero empty chunks both before and after. The cumulative empty-pool reclamation counter had reached 260,046,848 bytes (~248 MiB) by the first failure and 327,155,712 bytes (~312 MiB) by subsequent failures. This means the allocator has reclaimed wholly empty chunks earlier, but there are none available at the observed failures; further changes to retry policy or pool size are not supported by this capture.
- The Vulkan heap is reported as 7.76 GiB, while the contemporaneous DXVK budgets are about 3.89–4.00 GiB and driver budgets about 3.96–4.14 GiB. Driver budget reporting is not a guarantee that a single large allocation will succeed. The recorded failures are actual driver results, not DXVK's `budget_guard` path.
- The compiler configuration marker confirms `compiler_threads=4`. In the sampled pipeline-worker snapshots, normal-priority queue waits average roughly 0.34–0.52 ms and high-priority waits roughly 0.89–1.55 ms, while low-priority optimized-pipeline waits reach 8.04–11.07 ms average; 54 optimized jobs exceeded 10 ms and 12 exceeded 33 ms. This identifies a queue-wait imbalance worth investigating, but does not prove changing worker count or priority will improve frame time. Keep four workers as the current control: a prior eight-worker capture regressed badly.
- Pipeline lookup sampling reaches 3,440 samples with 97–100% last-hit-cache hits, mean scanned entries rounded to 0, maximum scan length 3, mean lookup time about 1.0–1.8 microseconds, and a 160.9-microsecond sampled maximum. **Defer the hash-indexed pipeline-variant table**: these measurements do not show enough linear scanning to justify its extra concurrency, lifetime, and memory complexity.
- GPU-wait samples reach 40,960; the final cumulative snapshot reports 2.875 ms mean, 91.712 ms maximum, and 343 waits over 33 ms. These waits and the allocation failures may both contribute to visible stalls, but the log alone cannot attribute individual frame spikes to one cause.

### Decisions after this capture

1. Do not change allocator block sizes, eviction policy, or budget enforcement: current failures are driver OOM responses with no empty chunks available to reclaim, not a false-positive DXVK budget guard.
2. Do not increase compiler threads based on queue backlog alone. Audit priority scheduling and on-demand compilation separately, and compare a matched four-worker baseline before changing it.
3. Keep the hash-indexed variant-table series deferred because the measured lookup scan is small and the last-hit cache is effective.
4. Preserve the current branch and Vulkan 1.3 baseline. The WCP allocation-trace and phase-0 builds passed on source commit `c6b1135f8378ca069c833c432143c78e07d60ae3` (runs [38889643669](https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38889643669) and [38889643714](https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38889643714)); telemetry tooling tests passed on log-only head `039a6779` (run [38891987510](https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38891987510)). The latest ledger-only commit has not been rerun through CI. No matched device A/B result or performance gain is established.

## Depth/stencil image barrier aspect correction (2026-10-16)

- Adapted upstream [`30f6f8338e3f88aadfd38aa8fc6fc0d35b1c70cc`](https://github.com/doitsujin/dxvk/commit/30f6f8338e3f88aadfd38aa8fc6fc0d35b1c70cc).
- When emitting an image access barrier for a depth/stencil format, the barrier range now includes the image format's complete aspect mask rather than only the tracked aspect. This addresses edge cases where a depth image is subsequently used as a compute resource and the barrier would omit the stencil aspect (or vice versa).
- Compatibility: uses existing Vulkan 1.3 barrier structures and no new extension or feature. This is a correctness/validation fix, not a performance claim.
- Validation: WCP x86/x64 builds; Vulkan validation where available; smoke tests for depth-only, stencil, and combined depth/stencil images, including render-to-compute transitions. Keep the change limited to the normal `accessImage` barrier path; layout-transition and transfer ownership paths have their own subresource semantics.

## Rasterizer discard for geometry shaders without position output (2026-10-16)

- Adapted upstream [`8bb499c546b1cefbbc588ea70ecb3086dfdc7f49`](https://github.com/doitsujin/dxvk/commit/8bb499c546b1cefbbc588ea70ecb3086dfdc7f49).
- If a geometry shader does not export `Position`, DXVK now enables rasterizer discard in the Vulkan rasterization state and marks the graphics pipeline as a discard pipeline. This avoids setting up rasterization state for output that cannot be rasterized; transform-feedback output remains supported by the existing path.
- The existing discard-state backport then omits irrelevant rasterization state and dynamic commands. No Vulkan feature newer than 1.3 is required.
- Expected benefit is limited to geometry-shader pipelines without position output (including upstream's stated D3D9 SWVP case); do not assume this is exercised by FFVII Remake or claim a game-level speedup without a matched capture.
- Validation: WCP x86/x64 builds; confirm the shader metadata marks `ExportsPosition` correctly for geometry shaders; test GS pipelines with/without position output, with transform feedback, and normal rasterizing GS pipelines.

## Resource-allocation reference-count release ordering (2026-10-16)

- Backported upstream [`8dc04230705481734d67875c34a7e8801c850c28`](https://github.com/doitsujin/dxvk/commit/8dc04230705481734d67875c34a7e8801c850c28): change the final resource-allocation reference decrement from acquire-only to release ordering, matching the upstream lifetime/allocator handoff semantics.
- This is a small atomic-ordering correction in the allocator's refcount path; it does not change allocation sizes, retry policy, or Vulkan API requirements. Treat any CPU-side performance effect as unmeasured.
- Validation: WCP x86/x64 builds, allocation/release stress, and device-side memory-pressure testing. Revisit if allocator stress or thread sanitizer testing identifies a lifetime-ordering concern.

## Throttle resource eviction batches (2026-10-16)

- Adapted upstream [`31c543361ef469cedbd0c4f56dc8dcbc8e60c6be`](https://github.com/doitsujin/dxvk/commit/31c543361ef469cedbd0c4f56dc8dcbc8e60c6be).
- In `DxvkRelocationList::poll`, resources marked `NoDeviceMemory` (eviction to system memory) count as 16 times their allocation size against the per-poll byte target. This deliberately overestimates relocation cost so one request does not process an excessive number of evictions at once.
- Expected benefit is less concentrated eviction/relocation work and potentially less stutter in memory-pressure scenarios. It does **not** create free memory immediately, change the Vulkan heap budget, or guarantee recovery from a single large allocation failure.
- This is a targeted scheduler heuristic, not a change to chunk sizing or allocator limits. Validate allocation retry counts, bytes relocated per poll, frame-time spikes, and OOM outcomes against the prior build under the same route and capture settings.
- Vulkan 1.3 API baseline unchanged.

## Prefer cached mappings for host-visible allocations on tilers (2026-10-16)

- Adapted upstream [`e3d3f69fe3707a6c0b6886262d404f5af92b4b33`](https://github.com/doitsujin/dxvk/commit/e3d3f69fe3707a6c0b6886262d404f5af92b4b33).
- Added a device performance hint that follows the existing tiler-mode classification and makes host-visible/coherent allocation lookups prefer the cached coherent memory-type mask when available. This is aimed at avoiding slow uncached CPU stores on ARM tiler systems such as Turnip/Adreno.
- If cached coherent memory is unavailable, the existing fallback to the coherent type remains. This changes memory-type preference, not Vulkan feature requirements, API version, or allocation budget.
- Expected benefit: lower CPU cost for mapped writes on supported memory-type layouts. This is hardware- and workload-dependent and is not yet measured on the Snapdragon 865. Monitor memory-type selections, CPU timing, and OOM behavior; ensure host-visible/coherent requirements remain satisfied.
- Validation: WCP x86/x64 builds; inspect target-device memory-type logs to verify the chosen type includes both `HOST_VISIBLE` and `HOST_COHERENT`, and `HOST_CACHED` when such a type is exposed.

## Include attachment reads in clear and render-pass barriers (2026-10-16)

- Adapted upstream [`49c5078886867e5f9ff5fc5107dc8dca7daec79a`](https://github.com/doitsujin/dxvk/commit/49c5078886867e5f9ff5fc5107dc8dca7daec79a).
- Clear operations now include attachment-read access along with attachment writes for color and depth/stencil. Render-pass attachment transitions likewise conservatively include read access; depth/stencil writes remain excluded for a read-only layout.
- The old load-op-based read-access inference was too narrow: attachment reads can occur as part of blending/depth-stencil tests even when the load op is not `LOAD`. More complete access masks improve synchronization correctness and Vulkan validation behavior.
- This does not change render-pass API requirements or introduce post-1.3 features. Validate color blending, depth/stencil tests, clear/discard operations, and read-only depth attachments on the target driver.

### Fork-specific adaptation

The relocation entry stores `DxvkAllocationModes` (a flags wrapper), not a single enum as in the upstream revision. The eviction throttle therefore tests the `NoDeviceMemory` bit with `.test(...)`, preserving combined relocation-mode flags.

## Preserve zeroMappedMemory's host-visible device-local fallback (2026-10-16)

- Follow-up to the cached-mapping tiler preference and upstream [d43594895e1c3036abbe323d1d33f373bcdddb85](https://github.com/doitsujin/dxvk/commit/d43594895e1c3036abbe323d1d33f373bcdddb85): when `dxvk.zeroMappedMemory` is enabled, first redirect the host-visible device-local lookup to the host-visible/coherent system-memory lookup, then prevent the tiler cached-memory hint from overwriting that choice. Cached coherent system-memory lookups remain preferred.
- This preserves the zeroMappedMemory policy while retaining the cached mapping preference for normal host-visible coherent allocations. It avoids forcing zeroMappedMemory allocations onto a device-local host-visible memory type merely because the tiler hint prefers cached mappings.
- Vulkan API baseline unchanged. Validate both settings combinations on the target driver, log selected memory types, and compare CPU zeroing cost, allocation failures, and memory pressure before claiming a performance benefit.


## Legacy descriptor-pool storage capacity adaptation (2026-10-16)

- Adapted the capacity correction from upstream [`84c34155aa093a55d2e57032c93696cae0899515`](https://github.com/doitsujin/dxvk/commit/84c34155aa093a55d2e57032c93696cae0899515) to this fork's six-type descriptor pool. Storage-image and storage-texel-buffer descriptor capacities now scale as `m_maxSets / 4` rather than `m_maxSets / 64` (16× more entries), matching the upstream correction without adding inline-uniform-block descriptors that this fork does not allocate.
- This changes descriptor capacity only; it does not enable newer Vulkan features or change `maxSets`. The larger per-pool reservation may increase driver-side pool memory, so this is not assumed to be a free optimization.
- Validation gate: x86/x64 WCP builds; inspect Vulkan allocation logs for `VK_ERROR_OUT_OF_POOL_MEMORY` / `VK_ERROR_FRAGMENTED_POOL` (the current allocator collapses allocation errors to a null handle); stress many storage-image/storage-texel descriptors and monitor pool memory and OOM behavior on Adreno 650. No performance gain claimed until a matched device A/B shows one.

## Persistent DXBC-to-SPIR-V shader-cache dependency audit (2026-10-16)

- Audited upstream `b705d4be48450ed53cf653ebfe408e3172f9d7bc` (per-device cached-shader API), `0bdba3659a25c59bb8e1b9d0efc0d544d88a8205` (cache serialization/thread/file implementation), and `bd20ebe959527cfa9bf59363caa125cb65230ecb` (D3D11 call site). The complete cache implementation is a substantial new subsystem, not a safe one-hunk backport. It also depends on shader IR serialization/metadata/layout formats and a compatible dxbc-spirv update; current 2.7.1 constructor side effects (shader dump, ICB allocation/upload, registration and binding masks) must remain correct on cache hits and misses.
- Disposition: continue the dependency audit, but do not introduce the persistent cache yet. Before implementation, map the exact 2.7.1-compatible dxbc-spirv revision and file/path APIs, verify all cache-key inputs, add cache format invalidation tests, and test cache corruption / unwritable-directory fallback. The change is expected to improve repeated shader translation/startup, but first-run compilation and Vulkan API compatibility are separate concerns.

## Pipeline variant hash-table audit (2026-10-16)

- Audited upstream `e40ba5f8b88dde90bb4293f5eaa1c3e41ed247b4` plus graphics/compute integrations `7f0c71c2e7dc10016c1050298eeb50cf096b7d67` and `9138d7cdf9af6f18d01b04116c29b7424e065046`. This is a concurrent adaptive table replacing linear variant lists and changes instance ownership/lifetime as well as lookup.
- Disposition: do not port based on the available FFVII Remake trace. Existing lookup telemetry reports 97–100% hits, mean lookup roughly 1–2 microseconds, and at most three scanned entries. The hash computation, table memory, atomic operations, and concurrency/lifetime risk are not justified by current evidence. Revisit only if a representative capture shows materially larger scan counts or lookup time.
