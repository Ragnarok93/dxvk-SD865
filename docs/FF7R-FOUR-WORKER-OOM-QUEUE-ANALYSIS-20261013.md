# FF7R SD865 four-worker diagnostic run — 2026-10-13

Source: three user-provided GameNative logs (`ff7remake__dxgi.log`, `ff7remake__d3d11.log`, Wine console). Do not publish Wine console raw: Epic launch authentication arguments are embedded.

## Build/config validation

- Loaded source SHA **4a65e1b33aae98dc91adf3ef1b8205b5f8623215** in **both** D3D11 and DXGI; logger contract `queue-sync-alloc-v2`.
- FF7R D3D11 feature level 11_0, Vulkan wrapper 26.2.99, graphics pipeline library available, DXGI output 1280x720.
- `DXVK-SD865-CONFIG`: `compiler_threads=4 source=ff7r-experiment-default`, `dxvk_config_present=1`, `override_present=0`, `metrics_enabled=1`, `alloc_trace_enabled=1`. GameNative's pre-fix `DXVK_CONFIG` value remains `""` in this capture, but the source-specific four-worker fallback worked.
- All intended trace events active. The repository/package identification fix is successful.

## Correctly interpreted CPU timing results

From 44 unique 256-present windows (11,264 measured CPU-side completion intervals), late-scene slowdown begins around `present_id=7170`. In the region with IDs 2306–6914, 19 windows have median-of-window P95 9.30ms; final eight windows median-of-window P95 62.85ms, average of window mean intervals 43.7ms. These are **not GPU execution timestamps or measured actual scanout FPS**.

Final asynchronous submission metrics (cumulative, not per-frame):
| Counter | Count | Mean CPU elapsed | Max CPU elapsed | >10ms | >33ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| ENQUEUE | 45,888 | 19us | 4,138us | 0 | 0 |
| QUEUE-SUBMIT | 45,888 | 93us | 6,361us | 0 | 0 |
| QUEUE-PRESENT | 11,264 | 703us | 43,166us | 1 | 1 |
| GPU-WAIT | 45,888 | 4,246us | 108,584us | 5,929 | 726 |

GPU-WAIT is elapsed host waiting for timeline semaphore completion, includes prior queued work and scheduler behavior, and must not be labeled direct GPU render duration. Queue submission/lock overhead does **not** dominate.

Last pipeline workers: 448 background tasks (262 GPL libraries averaging 2569us, 186 optimized tasks averaging 3818us), nine >10ms and zero >33ms. On-demand creation: 192 samples averaging 302us, zero >10ms. Four vs previous eight workers is **not a matched-scene A/B**: a decline from earlier 14 to 9 long compiler tasks is insufficient to assert a speedup.

## Confirmed driver allocation failure, not merely budget guard

Nine `DXVK-SD865-ALLOC stage=driver_retry` events returned first and retry `VkResult=-2 VK_ERROR_OUT_OF_DEVICE_MEMORY`, all `recovered=0`, on memory type 0, heap 0, `dedicated=0`, `pool_experiment=0`. Request sizes: 256MiB x4, 128MiB x3, 64MiB x2. The driver backend, not only DXVK's budget threshold, rejected these calls.

First event: `dxvk_allocated=3560964096`, `dxvk_budget=3993433867`; final: `dxvk_allocated=3829399552`, `dxvk_budget=4184274699` bytes; still some reported headroom (~338MiB at the last event). Resource heap was shared system RAM; residual budget does NOT guarantee a contiguous allocatable chunk. The log continues rendering after those events, so they cannot all be called terminal fatal errors.

The end of Wine capture again records X connection closure and `pthread_mutex_lock` on destroyed mutex. No `VK_ERROR_DEVICE_LOST` detected. No single event in logs establishes the *trigger* of X-server termination.

## Next defensible performance experiment

- Lock game scene, resolution/texture quality, shader cache, FEX, LSFG/vkBasalt, driver, and compiler count. Use same WCP with `DXVK_SD865_POOL_EXPERIMENT=0` vs `1` to isolate existing source-gated 64MiB device/32MiB mapped pool caps and eager reclamation. **Only if** the pool build's embedded identity and diagnostics are validated; the earlier pool workflow did not stamp `DXVK_SD865_BUILD_SHA`, unlike the verified phase0 WCP.
- Measure number and sizes of driver allocations, failed retries, peak DXVK allocated/budget, visual integrity, and identical-scene p95/p99, plus Android low-memory/driver logs where available.
- Once allocator issue is bounded, correlate GPU-WAIT with Vulkan GPU timestamp queries or driver-side profiler. Avoid inferring GPU-bound solely from host wait latency.
- Four/eight worker trial remains pending a controlled repeat. Avoid raising `dxgi.maxDeviceMemory`, forcing Vulkan heap budget or unconditional 64MiB policy without matched evidence.

No code or FPS improvement claimed in this checkpoint; it documents a successful diagnostics fix and the first confirmed Vulkan allocation failure results.