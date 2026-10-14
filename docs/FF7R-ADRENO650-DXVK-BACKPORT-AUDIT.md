# FFVII Remake / Adreno 650: DXVK backport and fork audit

Status: source-level triage against the current Vulkan 1.3-compatible DXVK 2.7.1-derived branch. This is a candidate ledger, not a claim that the listed changes improve FPS. Each runtime candidate still requires build, correctness, and matched Snapdragon 865 measurements.

## Scope and baseline

- Target: FFVII Remake in GameNative on Snapdragon 865 / Adreno 650 using Turnip.
- Compatibility invariant: retain the DXVK 2.7.1 ancestry and Vulkan 1.3 baseline. Do not copy later DXVK features merely because they exist in 3.1.1; first classify API/feature requirements and preserve a valid fallback.
- Telemetry branch: `feature/ff7r-adreno650-telemetry-20261014`.
- Comparison references:
  - Upstream 2.7.1: https://github.com/doitsujin/dxvk/releases/tag/v2.7.1
  - Upstream 3.1.1: https://github.com/doitsujin/dxvk/releases/tag/v3.1.1
  - DXVK-Sarek: https://github.com/furbi963/DXVK-Sarek
  - Sarek's asynchronous pipeline compilation introduction: https://github.com/furbi963/DXVK-Sarek/commit/d745699e003f2f97ac3294bdc519996137216a1f
  - Sarek's pipeline lookup/worker redesign: https://github.com/furbi963/DXVK-Sarek/commit/c919f0b44325e09c9fc5c88551d5076ea4f2906e
  - Sarek's lock-free queue/hash-map revision: https://github.com/furbi963/DXVK-Sarek/commit/0444d886ae845c9c911d84cf441fb62d6253745a
  - Upstream tiler render-area change: https://github.com/doitsujin/dxvk/commit/d92226b6a9e5ac7d9e9f00999b0feb54c9e1987e
  - Khronos tile-based rendering best practices: https://docs.vulkan.org/guide/latest/tile_based_rendering_best_practices.html
  - Khronos command-buffer recording and secondary-buffer guidance: https://docs.vulkan.org/samples/latest/samples/performance/command_buffer_usage/README.html
  - Khronos dynamic-state trade-offs: https://docs.vulkan.org/guide/latest/dynamic_state.html
  - Qualcomm Snapdragon Game Toolkit / Adreno developer guide (living documentation): https://docs.qualcomm.com/bundle/publicresource/topics/80-78185-2/
  - Qualcomm Adreno model-specific spec sheets (including A6x): https://docs.qualcomm.com/bundle/publicresource/topics/80-78185-2/spec_sheets.html?product=1601111740035277

## Findings

### 1. Tiler render-area handling — already present in the active diagnostic branch

The current branch selects secondary command buffers whenever `m_device->perfHints().preferRenderPassOps` is true. `DxvkDevice::getPerfHints()` sets this for Turnip. This matches the intent of upstream commit d92226b6a9e5: secondary command buffers on all tiler render passes so render-area trimming can be applied, including trivial/single-color passes.

**Disposition:** do not duplicate this patch. Keep it covered by the FFVII Remake regression run because it changes the render-pass recording path and can affect CPU cost or correctness.

### 2. Sarek dyasync — promising CPU-stall hypothesis, not safe to cherry-pick wholesale

The Sarek series makes pipeline-variant compilation asynchronous when a fallback pipeline exists, introduces separate live/background work queues, and changes pipeline instance lookup from a mutex-protected linear scan to an atomic hash-table lookup. This is relevant to Unreal Engine workloads because late pipeline variants can otherwise block the render thread.

However, the active DXVK-SD865 branch already has a different pipeline-library/base-pipeline path and optimized-pipeline worker implementation. Sarek's code was developed against a different DXVK lineage and cannot be transplanted as a clean commit. Its implementation also hashes the raw bytes of the pipeline state structure; padding/uninitialized-byte behavior, collision resolution, map overflow, queue deduplication, object lifetime, and driver concurrency all need explicit review before adoption.

The existing `DXVK-FF7R-ONDEMAND` timer measures the cache-miss slow path only. It does **not** measure the linear `findInstance` scan on cache hits, which is the hot path implicated by Sarek's write-up. A slow-path marker alone cannot establish that cache-hit lookup is expensive.

**Disposition:** the last-hit cache is enabled by default on the active branch; set `DXVK_FF7R_PIPELINE_LOOKUP_CACHE=0` to disable it for A/B testing. It stores a pointer to an append-only `sync::List` node, whose address remains stable until the parent pipeline is destroyed; the node's state key is immutable after publication, and no node is removed during normal use. The cached pointer is atomic. The optimization does not alter pipeline creation, handle ownership, or Vulkan synchronization. With `DXVK_FF7R_METRICS=1`, `DXVK-FF7R-LOOKUP` samples one in 256 calls and reports mean lookup nanoseconds, mean list entries scanned, and sampled cache-hit percentage. This is source-level architectural review only: Windows builds must pass, and Adreno 650 runtime correctness/performance still require matched tests. The default can be rolled back immediately with the environment override if device testing exposes a regression.

### 3.2 Telemetry opt-in consistency fix

A follow-up source audit found that the `DXVK_FF7R_ONDEMAND` setting was reported in the device-startup marker and documented as an opt-in, but the slow-path timing block was actually gated only by `DXVK_FF7R_METRICS=1`. The timing block now requires both `DXVK_FF7R_METRICS=1` and `DXVK_FF7R_ONDEMAND=1`, matching the runbook and avoiding unexpected slow-path timing/logging when on-demand diagnostics are not requested. This is a telemetry behavior correction, not a rendering-path optimization.

### 3.1 Low-risk branch-hint backport — dynamic-state dirty paths

Upstream commit [9d6b9fa](https://github.com/doitsujin/dxvk/commit/9d6b9fa5f7e43e67bce0307d04308dcf274deaa8) marks five dynamic-state update branches as unlikely: rasterizer state, stencil test/reference, depth bias, and depth bounds. The corresponding conditions were still unannotated in this fork, so the hints are now backported in isolation. This is compiler branch-prediction guidance only; it does not change state transitions or Vulkan command emission. Expected impact is small and workload/compiler dependent, and must not be represented as a measured FPS improvement.

**Disposition:** keep the change isolated; validate on x86/x64 CI, then check shader/render correctness and matched frame-time captures on Adreno 650. If compiler output or device traces show no meaningful effect, the change is harmless but not a priority for further tuning.

### 2.1 Candidates reviewed and deliberately not transplanted

- Upstream `bc94fe4` (push-data gather) and `398c950` (remove unused push-data members) are explicitly motivated by D3D9 content in the upstream descriptions. FFVII Remake uses the D3D11 path, so these are not justified as first-line optimizations for this workload. Their push-data layout and shader-IR changes are also coupled across `DxvkContext`, pipeline layouts, and DXBC-SPIR-V processing; do not cherry-pick only the visible copy-loop change.
- Upstream `bd4395a` (disable raster-related dynamic state when rasterizer discard is active) changes the relationship between pipeline creation flags, dynamic-state declarations, and context dirty flags. It is a potentially useful future backport, but not a safe isolated edit: this fork must preserve exact Vulkan dynamic-state validity for both pipeline-library and optimized-pipeline paths. Defer until those paths can be compared side-by-side and exercised with validation layers or focused regression coverage.
- Sarek's redundant `vkCmdBindPipeline` suppression remains deferred for the same architectural reason: actual command-buffer recording state, meta operations, and command-buffer reuse must all participate in invalidation.

### 3. Upstream 3.1.1 backports — classify by workload and API contract, not commit count

The 2.7.1-to-3.1.1 range contains hundreds of commits spanning D3D8/9/11, DXGI, Vulkan wrappers, shaders, build tooling, and game-specific compatibility. The compare endpoint reports 988 commits between those tags, so a blind aggregate merge is not an acceptable backport method.

First-pass relevant classes:
- D3D11 context/resource/state and DXGI present/swapchain changes: audit individually for hot-path overhead, correctness, and required Vulkan feature level.
- Pipeline-library and dynamic-state changes: confirm what is already in this fork before considering additional changes; the active branch already contains a pipeline-library path.
- Tiler/render-pass behavior: the upstream render-area secondary-command-buffer behavior is already present in the active branch.
- D3D9-only fixes, title-specific config profiles, and features requiring a higher Vulkan baseline: not FFVII Remake candidates unless a concrete dependency is demonstrated.

**Disposition:** create one small backport per identified behavior, each with an upstream commit link, API/feature requirements, a regression test, and an independent benchmark result. Avoid mixing synchronization, shader, and allocator changes in one patch.



### Redundant Vulkan pipeline-bind suppression — defer pending command-state audit

Sarek's redundant graphics/compute bind suppression is a plausible CPU-side optimization, but it is not enabled in this fork yet. The active context binds Vulkan pipelines from both ordinary D3D11 state updates and multiple internal meta operations (clear, blit, buffer/image transfer, and resolve paths). A correct cache must track graphics and compute bind points independently and invalidate state at every command-buffer reset/switch and every path that can bind a meta pipeline. Skipping a bind based only on `m_state.gp.pipeline`/`m_state.cp.pipeline` would be incorrect because those are D3D-facing pipeline objects, not necessarily the last Vulkan pipeline handle actually bound. The next implementation should put tracking at the command-buffer recording layer or prove complete invalidation coverage across all `cmdBindPipeline` call sites; do not copy Sarek's context-level change verbatim. Keep it isolated and add tests/counters for emitted versus skipped binds before enabling it by default.

## Ranked next experiments

| Priority | Experiment | Why it may matter | Main risk / gate |
|---|---|---|---|
| 1 | Profile pipeline cache-miss/lock stalls with `DXVK_FF7R_METRICS=1` and `DXVK_FF7R_ONDEMAND=1` | Identifies whether the render thread is blocked on pipeline lookup/creation rather than GPU work | Instrumentation is diagnostic only; compare low-overhead performance runs separately |
| 2 | Isolated Sarek-inspired pipeline lookup/queue prototype, only if traces justify it | Could reduce per-draw linear lookup and prioritize live variants over background compilation | State hashing, duplicate creation, worker races, pipeline lifetime, Turnip driver stability |
| 3 | D3D11 state/resource hot-path backports selected from upstream 3.1.1 | Can reduce CPU submission overhead if the target path exercises the changed code | Large source drift; require Vulkan 1.3-compatible implementation and focused tests |
| 4 | Staging/allocation/synchronization fixes only when wait counters or external traces identify them | May address CPU/GPU stalls without speculative scheduler changes | Never remove a wait or alter lifetime guarantees based on duration alone |

## Validation contract

- Build x86 and x64 artifacts from the exact commit; verify Vulkan 1.3 compatibility.
- Run FFVII Remake in GameNative on the same Adreno 650 device, using the same route, settings, resolution, Turnip revision, and thermal conditions.
- Separate cold-cache from warm-cache trials and use at least three matched trials per variant.
- Collect diagnostic logs and external frame-time traces. Do not treat DXVK CPU-side Present intervals as GPU execution or display-scanout time.
- Keep a patch only if median frametime and tail frametime (p95/p99) improve repeatably without crashes, artifacts, memory regressions, or worse sustained thermals.
- No performance gain has been established by this source audit alone.

## ARM64EC fork audit — CPU-usage candidates

Reviewed `JustCallMeJade/dxvk-arm64ec` (master, head `52fe923ca1496c8e44789b613fab8611dfcb5c4a`, 2026-09-25) against its fork-specific `JustCallMeJade-patch-1` branch. The branch comparison shows the fork-specific delta is build/release plumbing (`.github/workflows/build.yml`, `build-win64.txt`, `build.sh`, `meson.build`, `profile.json`), not a distinct runtime CPU-optimization patchset. The master branch contains a much newer upstream DXVK code line, so its runtime changes must be evaluated as upstream backports rather than attributed to ARM64EC-specific tuning.

Relevant source comparisons against this DXVK 2.7.1-based branch:

- D3D11 shader/resource state tracking already includes dirty-state checks and avoids redundant resource binds in common setters; do not transplant duplicate state tracking just because it appears in the newer fork.
- The newer D3D11 code reuses per-stage instance-data buffers for shader class-instance metadata. This reduces repeated buffer creation for dynamic shader linkage, but is a narrow path and is not presumed to benefit FFVII Remake without evidence that the game exercises class instances. Defer as a low-priority, separately testable backport.
- Newer DXVK context code batches resource-access declarations and clear operations and includes additional transfer paths. These changes span synchronization, command recording, and Vulkan feature handling; do not cherry-pick individual lines out of context.
- Newer presentation timing and swapchain changes are not automatically useful on Android/Turnip. Any candidate must be checked against the actual WCP Vulkan loader/driver capabilities and FFVII Remake's presentation path.
- The fork's D3D11 Vulkan interop buffer-lock additions are API/interop behavior, not a general CPU optimization for this workload.

### ARM64EC follow-up: verify existing lazy binding before porting

A targeted symbol-level inspection of the active branch confirms that the main candidate previously identified—lazy D3D11 resource binding—is already implemented here:

- `D3D11ContextState` contains `D3D11LazyBindings`, including per-stage `shadersUsed`, `shadersDirty`, `bindingsUsed`, and `bindingsDirty` masks.
- `D3D11CommonContext::DirtyBindingGeneric` tracks resource changes and defers selected null/inactive bindings.
- `ApplyDirtyGraphicsBindings` and `ApplyDirtyComputeBindings` flush dirty bindings immediately before draw/dispatch work.
- `DebugLazyBinding` is `Tristate::Auto`, so the default path uses the existing adaptive policy rather than forcing the more expensive always-track mode.

**Disposition:** do not port lazy binding again. The ARM64EC fork's shader class-instance buffer reuse is also deferred: the target path explicitly logs class instances as unsupported, making it unlikely to improve FFVII Remake. The reviewed fork does not currently provide a distinct, safe runtime CPU optimization that is both missing here and demonstrably relevant to this workload. Keep porting individually identified upstream changes only when they fit the Vulkan 1.3 baseline, and prioritize render-thread telemetry plus matched device measurements over speculative broad refactors. The FF7R last-hit pipeline cache remains a separate experiment with unmeasured performance impact.
