# FF7R S20+ — runtime WCP identification, config and OOM audit (2026-10-13)

## Symptom confirmed from user capture

The user installed our provided `a1ebd28` WCP and used the provided GameNative environment options. Nevertheless the observed game logs retained the **older untimestamped** `DXVK-FF7R-FRAMES: present_id=...` / `DXVK-FF7R-PIPELINES: samples=...` markers, contained **none** of the queue/CS/GPU wait markers already verified as present inside that WCP, printed `Found config env: ""`, and reported **eight** compiler workers. The trace ended with `DxvkMemoryAllocator: Memory allocation failed` for 22,437,888 bytes at 4096 alignment, eligible types 0/1/2, with heap allocated/used/reserved/budget at 3684/3286/3385/4153 MiB respectively. That is *not proof the Vulkan heap was completely full*, nor proof that the queue instrumentation caused the crash.

The on-device result did not match the delivered artifact. Prior build had no verifiable in-process commit stamp; logs alone could not distinguish a stale Wine DLL, mixed components, log capture from another process, or an install/selection issue.

## Corrective source changes

1. **Immutable in-process WCP identity:** `src/util/util_ff7r_build_stamp.h` begins as a clearly unverified sentinel; the FF7R GameNative phase0 workflow replaces it with the *exact* build commit SHA immediately before compilation. Its x32/x64 PE DLLs must embed the SHA and contract strings or CI rejects them. `DXVK-SD865-BUILD: component=d3d11 sha=...` and `component=dxgi sha=...` print regardless of `DXVK_FF7R_PHASE0`, as soon as device/swapchain paths execute. A missing marker or differing SHAs establishes a loader/path issue instead of a broken environment-variable test.
2. **Unambiguous compiler controls:** for `ff7remake_.exe`, DXVK uses **four** compiler workers when `dxvk.numCompilerThreads` was not validly set; source label `ff7r-experiment-default`. `DXVK_FF7R_COMPILER_THREADS` accepts a single digit 1–8 and takes precedence. Existing nonzero `dxvk.numCompilerThreads` remains supported, and other games retain upstream default. Startup always logs `DXVK-SD865-CONFIG` with effective worker count/source and whether `DXVK_CONFIG`, override, metrics and tracer were seen. Invalid override warns and falls back without exception.
3. **Allocation failure tracing self-contained:** `DXVK_SD865_ALLOC_TRACE=0` is the only opt-out. Otherwise bounded, failure-only diagnostic logs distinguish `stage=budget_guard`, `stage=driver_retry` with *actual first/retry VkResult*, `stage=pool_exhausted` and `stage=dedicated_exhausted`. The FF7R allocator prints one startup readiness marker. The diagnostics preserve DXVK allocation policy, fallback and Vulkan 1.3 compatibility.
4. CI contract/tests repaired for new default and labels. These are diagnostic/config corrections, not a claim of improved FPS, reclaimed memory or driver bugfix.

## Next A/B capture (once exact CI artifact is verified)

Install the uniquely labeled **`ff7r-verified-dxvk271-<sha12>.wcp`** and select it in GameNative. Keep low texture quality and unchanged Turnip, FEX, LSFG (resident but FG disabled), vkBasalt, scene, resolution.

Base env remains `DXVK_FF7R_METRICS=1` + `DXVK_LOG_LEVEL=info`; extra `DXVK_SD865_ALLOC_TRACE=1` is no longer necessary. Remove malformed `DXVK_CONFIG` value `""` if it is not used for other options; the new test does **not** depend on that setting.

**Test A:** No `DXVK_FF7R_COMPILER_THREADS` env: game should print `DXVK-SD865-CONFIG ... compiler_threads=4 source=ff7r-experiment-default`, unless a valid `dxvk.numCompilerThreads` override is already present.

**Test B:** `DXVK_FF7R_COMPILER_THREADS=8`, otherwise exactly same game and device parameters; game should print `compiler_threads=8 source=ff7r-env-override`.

Both captures must contain *identical* full `component=d3d11` and `component=dxgi` SHA matching the WCP. `DXVK-FF7R-FRAMES` must include `ts_us`; new queue markers print on activation. Any mismatch is a GameNative DLL activation/path defect and invalidates the benchmark. No further Turnip optimization should be attributed to this run until the WCP identity matches.

Never upload unredacted Wine cmdlines to public issue trackers: Epic exchange-code authentication values can be present in LSFG tracing.
