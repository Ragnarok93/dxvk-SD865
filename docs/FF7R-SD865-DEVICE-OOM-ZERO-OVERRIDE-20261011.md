# FFVII Remake on S20+ — 0-MB GameNative Graphics Override, Persistent Vulkan OOM

**Captured:** 2026-10-11 23:37 UTC; user supplied `ff7remake__d3d11.log` (126 lines), `ff7remake__dxgi.log` (4 lines), `wine_debug.log.txt` (751 lines), and the separate historical `pluvia_crash_2026-10-06_06-51-57.txt`. Private original logs are not committed.

## Controlled setting change

The user previously confirmed GameNative **Graphics → Max Device Memory** had been set to **2048 MB** for an earlier run. The new game log reports **Vulkan heap 0 size = 7951 MiB**, restoring the original non-2048 heap exposed by prior baseline runs. This is consistent with the proposed **Max Device Memory = 0 MB** graphics override experiment (GameNative UI writes `WRAPPER_VMEM_MAX_SIZE` only for positive values); the file itself does not dump the current UI value, so source and before/after signatures are the basis for that attribution. DXVK's `dxgi.maxDeviceMemory = 3072` **reported-DXGI-memory** option remains unverified from error-level logs.

**Actual counts** (counted from the supplied 126-line D3D11 log, not extrapolated):
- **94** `DXVK-SD865-ALLOC stage=driver_retry` events. All **94** have `first_vkresult=-2 retry_vkresult=-2 recovered=0`: two failed Vulkan calls per event (188 failed `vkAllocateMemory` calls observed, excluding unlogged successful calls).
- **8** `stage=pool_exhausted` events. Each terminal pool resource requirement requests `11,218,944` bytes (10.70 MiB) with 4096-byte alignment and `requested_memory_types_mask=7`, `eligible_memory_types_mask=7`.
- All **94** rejected allocation events have `dedicated=0 flags=2 buffer_usage=137727 heap=0`, meaning pooled buffer allocation requiring **`VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT`**; failure is observed across memory types **0 (46), 1 (24), 2 (24)**.
- Rejected chunk sizes: **256 MiB (10)**, **128 MiB (10)**, **64 MiB (26)**, **32 MiB (24)**, **16 MiB (24)**. Counts correspond to recorded retry *events*, not individual logical resource allocations: several failed chunk probes can be performed per `pool_exhausted`.
- First recorded failure occurs with DXVK **3908 MiB allocated**; latest occurs with **4004 MiB allocated**, **3787.45 MiB used**, approximately **216.55 MiB allocated-but-not-used**. Latest driver-advertised budget **4530 MiB**; DXVK internal budget ~4557.7 MiB. Current budget is still larger than DXVK-allocated total, but Vulkan `vkAllocateMemory` returns OOM.
- The final DXVK heap snapshot is **`0: 7951 4004 3787 3727 4530`**, columns (Size, Allocated, Used, Reserved, Budget) in MiB. The reported `Reserved` column comes from driver adapter memory usage and **must not** be conflated with DXVK unused pool slack.
- The main Wine log independently duplicates the 94 failures and 8 pool exhaustion events and ends with Wine error helper output followed by X server disconnection. No explicit native game crash stack or true physical driver OOM cause has been captured.
- The DXGI companion log contains only EDID parsing/colorimetry fallback. The October 6 `pluvia_crash` Java JNI `UnsatisfiedLinkError` remains a separate historical Android app issue.

## Interpretation vs earlier override test

The **2 GiB heap was an intentional reporting override**, not a new GPU hardware ceiling. Restoring the original 7951 MiB heap does **not** eliminate driver OOM at approximately 4 GiB DXVK allocations. The earlier 2 GiB run captured **105 driver_retry** events and **23 pool_exhausted** events, and hit the global 128-event log cap; **do not** interpret raw event counts as failure frequency or performance improvement without matched run duration and an uncapped per-process event tally. Here the failure-only trace recorded 102 diagnostic events, below the cap.

The evidence supports: an effective driver/system per-process/BO address-space/memory-pressure constraint or fragmentation, shared Android system memory pressure, or long-lived global pool retention. **It does not prove** that an absolute 4-GiB memory ceiling exists, nor that the buffer device address flag causes it (flag also exists on successful allocations), nor that a game-facing DXGI 3072 MiB setting was applied.

## Source-level next experiment (not yet implemented)

Upstream-derived fork `src/dxvk/dxvk_memory.cpp`:

- `determineMaxChunkSize` permits a **256 MiB device pool** and **64 MiB mapped pool** on a 64-bit host; `allocateChunkInPool` starts at the chosen target and halves on driver OOM until no viable chunk fits.
- `freeEmptyChunksInPool` retains up to **one device-pool max chunk** or **four mapped-pool max chunks** *per memory type* before freeing empty chunks (unless other conditions force freeing). Under an effective ~4GiB driver OOM constraint, this may leave significant retained **wholly empty** Vulkan allocations, although DXVK's allocated-versus-used difference also includes partially occupied chunks which this policy cannot free.
- For an isolated, **opt-in DXVK-SD865 test WCP**, reduce max global **device pool** chunks to **64 MiB** and **mapped pool** chunks to **32 MiB**, and allow zero *fully empty* chunk retention by a feature gate. Preserve page-allocation correctness, Vulkan BDA flags, memory types, and all existing OOM cleanup/retry semantics. Make a separate unique WCP (not silently changing the known diagnostic reference build).
- Add one low-noise startup marker showing mode and max device/mapped pool sizes, plus counters for whole empty chunks reclaimed and success/failure at the final allocation. Test parser and source contracts, and compile both x64/x86 DXVK DLLs before releasing. **Do not present test code as a confirmed fix**.
- Compare A/B at matched game scenes and graphical settings: first OOM at DXVK allocated/used totals, game progression, device heap-size report, number of recovered retries, crash/hang, and visible texture correctness. If still near 4 GiB live demand, revisit Android/Turnip driver kernel BO limits and game resource streaming; do not spoof reported memory.

**No new allocator behavior was implemented by this research commit.** References: `docs/FF7R-SD865-DEVICE-OOM-CONFIRMED-20261011.md`, `docs/FF7R-SD865-DEVICE-OOM-SECOND-RUN-20261011.md`, `docs/FF7R-SD865-VRAM-OVERRIDE-2GIB-20261011.md`.
