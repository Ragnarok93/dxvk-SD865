# FFVII Remake / SD865 pool WCP control A — 2026-10-13

User-uploaded files: `wine_debug.log (5).txt`, `ff7remake__dxgi.log`, `ff7remake__d3d11.log`. Comparison source (preceding upload): `wine_debug.log (3).txt`. **Do not copy or publish raw Wine logs**: they include an Epic AUTH_PASSWORD exchange-code value and user identifiers.

## Control validation (critical)

Both DXGI and D3D11 identify SHA `749729333e9b7cfddc427c8fc57cb24b7cb5f3ce`. First-party diagnostics confirmed. `DXVK-SD865-POOL state=init enabled=0 device_pool_cap_bytes=268435456 mapped_pool_cap_bytes=67108864 empty_chunk_policy=dxvk_default`. Therefore this was **control A using the experimental-WCP binary with optimization OFF**, NOT an enabled 64/32MiB candidate result.

Other observed state: FF7R D3D11 feature level 11_0, Vulkan wrapper 26.2.99, 1280x720 swapchain, 4 compiler threads (`source=ff7r-experiment-default`), metric and fail-only allocation trace active; LSFG resident/off and vkBasalt loaded. Old GameNative emits `Found config env: ""` but the FF7R override is active. Start DXVK heap0 budget 5,276,948,235B vs preceding baseline 4,902,606,603B (additional 357MiB), a confounder.

## Driver allocation failure evidence

New control: **13** failure-only `stage=driver_retry` sequences, all first and retry `VkResult=-2 VK_ERROR_OUT_OF_DEVICE_MEMORY`, `recovered=0`, on memory type 0, heap 0, non-dedicated. Failed requests 256MiB x5; 128MiB x4; 64MiB x3; 32MiB x1. `pool_experiment=0`; `empty_chunks_reclaimed=0`. Previous 4-worker non-pool run: 256MiB x4; 128MiB x3; 64MiB x2 (nine sequences).

First new failed sequence is in wine log between present IDs **14082–14338**, all others at 14082–14338 or 15362–15618. First previous failure was between IDs **9730–9986**. These are NOT aligned gameplay scenes or equal amounts of wall-clock play. Latest run continues to submit and present after allocation failures; final console reports X connection closure and a pthread mutex destroyed error (not an established DXVK/Turnip fault).

The new 32MiB driver failure is important: 64MiB/32MiB pool policy may reduce high-amplitude 256MiB chunk allocation/retry attempts, but cannot be assumed to cure general host/shared-memory pressure or small-size allocation failure.

## Presentation cadence

The latest `ff7remake__dxgi.log` has **61** separate 256-present windows (15,616 intervals), last full window present_id=15618. First captured baseline: 44 windows (11,264 intervals). Each window reports presentation CPU-completion intervals, **not GPU shader time or real scanout FPS**.

Latest sequence:
- Present IDs 1282–7682 (26 windows): median window p95 **36.19 ms**; median of window means **33.34 ms** — near-30fps pacing.
- IDs 8194–12546 (18 windows): median window p95 **10.37 ms**; median mean **7.72 ms** — distinct fast-paced workload/scene.
- IDs 13058–15618 (11 windows): median p95 **59.08 ms**; median mean **38.47 ms** — severe late deterioration.
- Last eight windows: median window p95 **64.94 ms**, compared with preceding capture last-eight-window median P95 **62.85 ms**. Windows occur at unrelated present IDs and are **not matched gameplay**.

At equal present_id the previous run's intervals were inverted: IDs 2306–6914 median P95 previously ~9.30 ms and now ~36.09ms, whereas IDs 7170–11266 previous ~51.13ms and now ~10.73ms. This shows that matching solely by presentation sequence **does not align scene/time** and invalidates interpreting the large cross-run differences as pool gains or regressions.

## Queue and compiler observations (cumulative)

| Event | Prior 4-worker run | New control |
| --- | ---: | ---: |
| enqueue samples | 45,888 | 64,192 |
| enqueue mean us | 19 | 19 |
| queue submit mean us | 93 | 101 |
| submit operations over 10 ms | 0 | 0 |
| completion-wait mean us | 4,246 | 4,315 |
| completion waits > 10 ms | 5,929 (12.92%) | 10,403 (16.21%) |
| completion waits > 33 ms | 726 (1.58%) | 755 (1.18%) |
| background compile tasks | 448 | 448 |
| background compile tasks > 10ms | 9 | 12 |
| on-demand compile samples / mean | 192 / 302 us | 192 / 233 us |

Percentages reflect different scenes and capture lengths; **neither performance gain nor regression is proven**. Queue CPU overhead remains far smaller than CPU-side present windows, whereas GPU completion waits periodically spike, though host wait is not a direct GPU execution-timing probe.

## Next required B arm

Use *the same* `ff7r-pool64m32m-dxvk271-749729333e9b.wcp`, *same Turnip*, cache/FEX/settings, same 4 compilation threads, LSFG resident/off, vkBasalt, same in-game save/scene and scripted camera path. Set just `DXVK_SD865_POOL_EXPERIMENT=1`; game must print `DXVK-SD865-POOL state=init enabled=1 device_pool_cap_bytes=67108864 mapped_pool_cap_bytes=33554432 empty_chunk_policy=reclaim_all_wholly_empty`. If the log still says `enabled=0`, stop comparison: env propagation failed.

Compare exact failing sizes/counts, first failure scene/time, reported budgets/used memory, empty-chunk reclamation, visual correctness and frame-window p95/p99 for **matched scenes only**. Capture an Android low-memory/driver diagnostic if feasible. Do not enable 64/32 policy by default or make Turnip allocator changes without this evidence.
