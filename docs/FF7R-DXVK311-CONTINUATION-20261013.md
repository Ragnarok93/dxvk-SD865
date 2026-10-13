# DXVK 3.1.1 continuation: concurrent optimized pipeline compilation

Starting head: d5814226. Branch: feature/ff7r-sd865-architecture-20261011.
Target: FF7R / GameNative / Snapdragon 865 / Adreno 650 / Vulkan 1.3.

## Refreshed fork survey before implementation

The prior survey and selective backports remain in FF7R-DXVK311-BACKPORT-PROGRESS-20261013.md.
Repository searches: `dxvk adreno fork:true`, `dxvk snapdragon fork:true`,
`dxvk android fork:true`, `dxvk arm64ec fork:true`, `dxvk binsem fork:true`.
Refreshed public histories on 2026-10-13:

| Source | Pinned head | Disposition |
| --- | --- | --- |
| doitsujin/dxvk v3.1.1 | b1a1c99a | Full v2.7.1..v3.1.1 ancestry inventory; select cc418519 (concurrent optimized variants). |
| winhub-emu/vegas | 49c2ac40 | Unchanged since prior code review; draw skipping, bind elision and memory cap remain excluded pending rendering/performance evidence. |
| isygold/Vegas-Private | 6b58f711 | Unchanged since prior source review; no new A650 patch identified. |
| Digger1955/dxvk-gplall | 6a0ea561 | Unchanged; state-cache/GPLAsync/latency changes are separate experiments, not required 1.3 replacements. |
| JustCallMeJade/dxvk-arm64ec | 52fe923c | No newer A650-specific fix in refreshed history; retain current x32/x64 packaging. |
| ValveSoftware/dxvk default proton_6.3 | 78ef4cfd | Old default branch; not evidence for modern Adreno performance. |
| HansKristian-Work/dxvk | eacc73f9 | Legacy upstream work; no new A650-specific implementation identified. |
| icyllite/DXVK-Sarek | d96fae37 | Vulkan 1.1 / DXVK 1.10 compatibility path; not an FF7R 2.7.1 performance transplant. |
| AndreVto/dxvk-android | README/source workflow | Android packaging of modern upstream, no demonstrated A650 lowering/performance fix. |
| nostalgia296/FEX-DXVK-BUILD | README | Architecture/build packaging only. |
| nlsidf/vulkan-adreno-shim | f84a865b | Separate driver wrapper, older A540/mapping work; no DXVK core backport. |
| Pixelgamer4k/HelixForge | d3819eb7 | Separate DX12 interception project, outside FF7R D3D11 core. |
| npark2860-cyber/DXVK_Adreno | empty search result repository | No source available to review. |

Coverage is the identified relevant public fork set, not every unindexed/private
repository. GPLAsync source rechecked at 04e50ed2 (2026-09-19), including the 2.7.1 and 3.1.1 patches; asynchronous draw/compile behavior remains a separate candidate requiring rendering acceptance.

## Selected change and compatibility

Upstream cc418519 permits different optimized variants of one shader pipeline to
compile concurrently while deduplicating identical keys. The 2.7.1 pipeline key
already supports this model; no shader compiler or device-feature change is needed.
Adapt publication to use a stable map-value pointer after unlocking: unordered_map
rehashing invalidates iterators but not pointers/references to elements. Publish a
terminal failure on exceptions as well, so duplicate requests cannot spin forever.
Validate distinct-key overlap, same-key deduplication, failed/throwing compiles,
and map rehash while a compilation is in progress. Cross-build both PE architectures.

Excluded: c276b56b flush-dropping heuristic targets Unity multisample resolves and
explicitly warns of possible deadlocks; not justified for FF7R. Access-tracker,
descriptor-heap, storage8 and new compiler series remain deferred. No feature spoofing.

## Acceptance / progress

- [x] Recover previous branch and survey ledger.
- [x] Refresh relevant fork histories and upstream ancestry before editing code.
- [x] Native concurrency regression fails on old serialized code and passes on adapted code; 50 tests pass.
- [x] MSVC x86/x64 and MinGW x32/x64 pass; GameNative WCP package checks pass.
- [x] DXVK source checkpoint dfcab832; MSVC builds passed before Turnip code changes, WCP validation also completed.
- [ ] Device real-frame median/p95/p99 and visual/stability acceptance.

LSFG/vkBasalt enabled in-container; LSFG FG disabled in-game; textures Low.
Keep resolution, scene, FEX, thermal state and cache state matched; measure each
subsystem independently. Compilation overlap is host evidence, not a device FPS claim.


## Build and review result

Source: dfcab83297c9517832f5fecac8e93b8bfa8e60df.
CI: https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38353184245 (success).
MSVC: https://github.com/Ragnarok93/dxvk-SD865/actions/runs/38353184209 (success).
Artifact ID11791789078; WCP dxvk-ff7r-phase0-dxvk271-dfcab83297c9.wcp.
SHA256: ce96a3cbfca452452aff50eff7b4882327fb4b839463d3f4a248119f8b4e1047.
Downloaded archive digest verified, WCP profile names exact source, and required
x32/x64 PE DLL headers verified. Existing Vulkan minimum/device feature checks,
shader compiler, descriptor model and compiler-thread settings unchanged.

Review: legacy getCode decompresses into a per-call buffer and patches that copy;
pipeline bindings are immutable after construction; worker queues retain pipeline
lifetime, and all result publication uses release/acquire. Map value pointer is
retained across rehash. Failed compiles remain terminal for that fast key, matching
the upstream completion model. Same-key callers can spin/yield while compiling;
FF7R duplicate frequency and CPU/frame-time benefit still require device evidence.

This completes this independent backport slice. Large access-tracker/compiler/
descriptor redesigns and the remaining candidate inventory are not asserted complete.
