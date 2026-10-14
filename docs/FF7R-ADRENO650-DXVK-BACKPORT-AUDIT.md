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

## Findings

### 1. Tiler render-area handling — already present in the active diagnostic branch

The current branch selects secondary command buffers whenever `m_device->perfHints().preferRenderPassOps` is true. `DxvkDevice::getPerfHints()` sets this for Turnip. This matches the intent of upstream commit d92226b6a9e5: secondary command buffers on all tiler render passes so render-area trimming can be applied, including trivial/single-color passes.

**Disposition:** do not duplicate this patch. Keep it covered by the FFVII Remake regression run because it changes the render-pass recording path and can affect CPU cost or correctness.

### 2. Sarek dyasync — promising CPU-stall hypothesis, not safe to cherry-pick wholesale

The Sarek series makes pipeline-variant compilation asynchronous when a fallback pipeline exists, introduces separate live/background work queues, and changes pipeline instance lookup from a mutex-protected linear scan to an atomic hash-table lookup. This is relevant to Unreal Engine workloads because late pipeline variants can otherwise block the render thread.

However, the active DXVK-SD865 branch already has a different pipeline-library/base-pipeline path and optimized-pipeline worker implementation. Sarek's code was developed against a different DXVK lineage and cannot be transplanted as a clean commit. Its implementation also hashes the raw bytes of the pipeline state structure; padding/uninitialized-byte behavior, collision resolution, map overflow, queue deduplication, object lifetime, and driver concurrency all need explicit review before adoption.

The existing `DXVK-FF7R-ONDEMAND` timer measures the cache-miss slow path only. It does **not** measure the linear `findInstance` scan on cache hits, which is the hot path implicated by Sarek's write-up. A slow-path marker alone cannot establish that cache-hit lookup is expensive.

**Disposition:** the telemetry branch now adds `DXVK-FF7R-LOOKUP`, sampling one lookup in every 256 calls when `DXVK_FF7R_METRICS=1`. It reports sampled CPU nanoseconds and entries scanned while leaving the normal lookup loop unchanged when metrics are disabled. This is diagnostic instrumentation, not a speedup. If matched captures show lookup cost is material, prototype a separate opt-in hash-lookup experiment that preserves the current synchronous fallback when no safe fallback exists. Do not replace the current pipeline manager wholesale.

### 3. Upstream 3.1.1 backports — classify by workload and API contract, not commit count

The 2.7.1-to-3.1.1 range contains hundreds of commits spanning D3D8/9/11, DXGI, Vulkan wrappers, shaders, build tooling, and game-specific compatibility. The compare endpoint reports 988 commits between those tags, so a blind aggregate merge is not an acceptable backport method.

First-pass relevant classes:
- D3D11 context/resource/state and DXGI present/swapchain changes: audit individually for hot-path overhead, correctness, and required Vulkan feature level.
- Pipeline-library and dynamic-state changes: confirm what is already in this fork before considering additional changes; the active branch already contains a pipeline-library path.
- Tiler/render-pass behavior: the upstream render-area secondary-command-buffer behavior is already present in the active branch.
- D3D9-only fixes, title-specific config profiles, and features requiring a higher Vulkan baseline: not FFVII Remake candidates unless a concrete dependency is demonstrated.

**Disposition:** create one small backport per identified behavior, each with an upstream commit link, API/feature requirements, a regression test, and an independent benchmark result. Avoid mixing synchronization, shader, and allocator changes in one patch.

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
