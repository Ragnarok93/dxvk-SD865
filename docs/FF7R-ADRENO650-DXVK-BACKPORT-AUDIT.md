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



### Redundant Vulkan pipeline-bind suppression — command-list prototype, opt-in only

An opt-in prototype now tracks the **actual Vulkan pipeline handle** independently for graphics and compute bind points, per DXVK command-buffer slot, at the shared `DxvkCommandList::cmdBindPipeline` recording wrapper. This covers ordinary D3D11 pipeline binds and internal meta-operation binds routed through the wrapper, rather than inferring Vulkan state from D3D11 context state. The cache is invalidated when a command-buffer slot is newly allocated, replaced by `next()`, initialized, finalized, or reset. Other bind points are passed through unchanged.

The feature is **off by default**. Set `DXVK_FF7R_SKIP_DUPLICATE_BINDS=1` to enable it; the startup marker reports the effective setting. With `DXVK_FF7R_METRICS=1`, `DXVK-FF7R-BINDS` reports aggregate emitted/skipped bind counts every 1,048,576 bind attempts. Leave metrics disabled for performance runs because logging/counter instrumentation perturbs the hot path.

This prototype is not yet a performance result. The first gate is the existing x64/x32 GameNative WCP CI build. The next gate is matched Adreno 650 correctness testing with the feature off/on, including render-pass changes, clears/blits/resolves, compute meta operations, command-list flushes, and long-session stability. Only consider changing the default after those runs demonstrate no rendering regressions and a repeatable CPU/frame-time benefit. Roll back immediately by omitting the variable or setting it to `0`.

## Sarek dyasync worker policy versus the existing compiler

Sarek's March 2026 dyasync notes describe separate live/background queues and workers that avoid selecting pipelines already being compiled. The target already has three priority buckets (`High`, `Normal`, `Low`) in `DxvkPipelineWorkers`, worker wake-up selection by priority, and a separate FFVII Remake compiler-thread override. On `ff7remake_.exe`, the current diagnostic default is four compiler workers when `dxvk.numCompilerThreads` is not explicitly configured; `DXVK_FF7R_COMPILER_THREADS=1..8` provides an A/B override. Thus, copying Sarek's queue split wholesale would duplicate existing priority behavior and interact with the branch's current pipeline-library/base/fast pipeline lifecycle.

The remaining potentially useful Sarek idea is worker-side avoidance of contention when several workers are eligible for queued work. That is a separate hypothesis from reducing render-thread lookup cost. Do not change worker selection until telemetry captures worker counts, queue backlog/wait time, pipeline compile duration, and render-thread stalls; otherwise a CPU-utilization reduction could simply move compilation later and increase first-use stalls.

**Disposition:** no worker scheduling code change in this pass. Use the existing `DXVK_FF7R_COMPILER_THREADS` override for controlled 2/4/6/8-worker captures, with identical scene, cache state, and run duration. The current four-thread setting is a diagnostic baseline, not a proven optimum.

## Deeper Sarek lock-free lookup review — algorithm useful, table sizing unsuitable to copy verbatim

Reviewed Sarek commits [c919f0b](https://github.com/furbi963/DXVK-Sarek/commit/c919f0b44325e09c9fc5c88551d5076ea4f2906e) and [0444d88](https://github.com/furbi963/DXVK-Sarek/commit/0444d886ae845c9c911d84cf441fb62d6253745a), which introduce the newer dyasync worker/lookup redesign. Its graphics-pipeline lookup table is not just a hash map: it includes a 4096-entry primary map, an 8192-entry overflow map, a 2048-entry fallback map, and a 4096-entry queue-deduplication set, with bounded probing and compatibility checks. The instance hash includes both the pipeline-state bytes and render-pass identity because that fork's pipeline instance API is render-pass-specific.

On a 64-bit build, the two atomic fields in each primary/overflow entry alone imply roughly 64 KiB + 128 KiB; the fallback map and queue-deduplication array add roughly another 80 KiB before padding and other fields. This is approximately 270 KiB of lookup-related arrays **per graphics-pipeline object**. That footprint is an important concern for an Android emulator workload with many pipeline objects and limited memory headroom. Copying the table sizes verbatim could trade CPU scans for substantial persistent memory growth.

The insertion path also publishes a hash before storing the corresponding instance pointer. Readers use acquire loads and check for a non-null pointer, but this transient publication window and the duplicate-creation/recheck paths must be understood and stress-tested rather than assumed safe solely because the table uses atomics. Sarek's overflow, fallback, and queue-deduplication maps are coupled to its altered asynchronous compiler flow, so importing only a subset would not preserve the design's full invariants.

### Recommended adaptation if FFVII telemetry justifies it

Do not port Sarek's full map. Prototype a much smaller per-pipeline index (start with 256 or 512 slots, not thousands), retaining the existing last-hit fast path and linear scan as a correctness fallback whenever probing misses or the table fills. Hash exactly the state fields used by target equality; never treat a hash match as equality. Before enabling it by default, measure per-object memory, lookup hit rate, and scan reduction, and test collision-heavy states, a full table, concurrent insert/find, pipeline creation failure, and destruction/lifetime behavior. The existing telemetry gate remains mandatory: if cache misses are rare or scan costs are insignificant in an actual FFVII Remake capture, keep the simpler implementation.

## Legacy DXVK-async fork audit — not a compatible backport source

Reviewed [Sporif/dxvk-async](https://github.com/Sporif/dxvk-async). Its README's compatibility matrix ends at DXVK 1.10.3 and describes a patch that makes pipeline compilation asynchronous, writes asynchronous pipelines into the state cache, and adds a separate compiler-thread setting. It also explicitly notes that its async mode disables graphics pipeline libraries because the two paths were incompatible in that implementation.

That work demonstrates the general stutter-reduction strategy, but it is not a viable direct backport to this 2.7.1-derived branch: pipeline creation, state caching, compiler worker scheduling, and GPL behavior have changed substantially since the supported 1.x line. The active branch already has base-pipeline/optimized-pipeline handling and prioritized worker queues; transplanting the old patch would risk bypassing those invariants and could force off a pipeline-library path already used here.

**Disposition:** do not port the legacy patch. Sarek's newer async compilation/priority design remains the more relevant reference, but any queue-policy change must be independently justified by FFVII Remake telemetry and reviewed against this branch's existing worker lifecycle. The current next gate remains collecting a representative `DXVK-FF7R-LOOKUP` / on-demand capture before changing lookup or scheduling behavior.

## Additional upstream 3.1.1 candidate triage — D3D11 and pipeline state

A targeted source/diff review of additional commits in the 2.7.1 → 3.1.1 range found these candidates. They are deliberately classified rather than bulk-backported.

### D3D11 indirect draw-buffer validation removal — reject as a performance-only backport

Upstream commit [c8c49cc](https://github.com/doitsujin/dxvk/commit/c8c49cc156f5044f9046ae5a8396a3a3aec2ed00) removes front-end `ValidateDrawBufferSize` checks from indirect draw/dispatch calls while widening the stored indirect-command offset to `VkDeviceSize`. The active branch still performs these checks in `D3D11CommonContext::DrawIndexedInstancedIndirect` and related indirect entry points.

This is not a clean CPU optimization to transplant by itself: the wider offset is part of the same correctness change, and removing validation changes behavior for undersized argument buffers. The current implementation batches adjacent indirect commands, so any future backport must also verify that the widened offset/stride calculations preserve batching boundaries and that invalid buffers are handled safely downstream. No FFVII Remake trace currently establishes that these calls are frequent enough to justify this behavior change.

**Disposition:** keep the validation. Revisit only if an FFVII trace identifies this path as material and the complete upstream change can be ported with boundary tests for null buffers, offset overflow, undersized argument buffers, and batched commands.

### Rasterizer-discard pipeline-state reduction — retain as a separate deferred patch

Upstream commit [7926853](https://github.com/doitsujin/dxvk/commit/7926853af7f3e9a05e9e9c94928a85cbada6b501) avoids passing viewport, multisample, depth/stencil, color-blend, and render-target state for rasterizer-discard pipelines and returns early while assembling rasterization state. The active branch already has `HasRasterizerDiscard`-specific dynamic-state handling and attachment-mask shortcuts, but its pipeline create-info path still supplies several of those structures.

This could reduce pipeline-state variation and Vulkan driver work for pipelines that truly discard rasterization. It is not equivalent to deleting fields mechanically: the `pNext` chain, descriptor flags, dynamic-state declarations, pipeline-library path, and the exact Vulkan 1.3 rules must remain valid. It is also not known whether FFVII Remake creates enough such variants to matter.

**Disposition:** candidate for a small, isolated future patch—not included in this pass. Add a focused test/validation run for discard pipelines and pipeline-library enabled/disabled paths, then compare pipeline counts and compilation time before deciding whether to keep it.

### Skyrim-specific cached dynamic resources — do not generalize

Upstream commit [878473b](https://github.com/doitsujin/dxvk/commit/878473bafd6e0595ffd71eff0e6b2d9e45f00a20) enables `d3d11.cachedDynamicResources` through a Skyrim SE executable profile. This is a title-specific configuration workaround, not evidence of a generally beneficial default for Unreal Engine or FFVII Remake. Do not copy the profile or force the setting globally without an FFVII-specific resource-update trace and memory/latency A/B data.

**Disposition:** reject as a global/default backport.

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

### Sarek dyasync follow-up: isolate the remaining lookup bottleneck

A fresh comparison of Sarek commit `c919f0b44325e09c9fc5c88551d5076ea4f2906e` and its lock-free lookup revision `0444d886ae845c9c911d84cf441fb62d6253745a` against the active branch confirms that some of the problem is already mitigated, but not eliminated:

- The active branch has an atomic last-hit pointer cache in `DxvkGraphicsPipeline::findInstance`. Repeated identical state can return in constant time without scanning the instance list.
- On a last-hit miss, the active branch still linearly walks `m_pipelines`. The optional `DXVK-FF7R-LOOKUP` sampler records scan length and elapsed time every 256 lookups. It must be used to establish whether misses are common and costly before expanding the cache.
- Sarek replaces the full lookup with a fixed-size open-addressing table plus an overflow path. Its change also touches asynchronous queue deduplication, pipeline compilation, and worker behavior; the commit is not a self-contained lookup-only patch.
- Sarek's implementation computes a hash from pipeline-state bytes. The target's equality operation is bytewise too, but copying the table without proving initialization/canonicalization, publication order, collision handling, overflow behavior, and pipeline-instance lifetime would still be an unnecessary correctness risk.
- The active branch's existing compiler has priority buckets and a separate on-demand path; Sarek's live/background queue policy should be evaluated independently from its lookup table rather than transplanted as one combined series.

**Next implementation gate:** collect a representative FFVII Remake log with `DXVK_FF7R_METRICS=1`, and compare `DXVK-FF7R-LOOKUP` mean/max time, mean entries, and cache-hit percentage. If list scans remain material, implement the lookup table as a separately reviewable change with a canonical state hash, bounded probing plus safe fallback, release/acquire publication, and tests for collisions, full-table behavior, concurrent insertion, and cache invalidation/lifetime. Keep the current last-hit cache as the fallback and require a successful GameNative WCP build before device A/B testing. Do not claim a CPU win until matched captures confirm it.
