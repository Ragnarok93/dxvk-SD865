# FF7R Adreno 650 render-pass attribution

Based on exact installed source 749729333e9b7cfddc427c8fc57cb24b7cb5f3ce, not the reduced-log-cadence candidate. All existing timing counters retain their original cadence.

Opt-in environment: `DXVK_FF7R_RENDER_PASSES=1`. Only literal `1` enables it; fixed for the process lifetime. No automatic environment/container edits.

`DxvkCommandList::cmdBeginRendering` records the final VkRenderingInfo immediately before dispatch. This catches secondary-command-buffer late load/store/clear/discard/resolve decisions, unlike logging the provisional state at renderPassBindFramebuffer. Every observed pass has a process-global atomic pass ID and monotonic CPU timestamp shared with its attachment records. Depth and stencil are separate aspects even when they share a view. Null color slots are explicitly marked unbound.

Records expose render area, layer count, view mask, flags, color count, attachment layout/load/store ops and resolve mode/presence/layout. Numeric operations are Vulkan enum values. They do not reveal format, sample count, actual bytes transferred, shader cost, GPU duration, executed-pass completion or scanout. Draw/dispatch and barriers are not modified. Logging CPU overhead and inter-thread line interleaving exist; group by pass ID, not line adjacency. Timestamp and pass ID ordering can differ across threads.

## Validation and next experiment

Native mock tests compile the actual wrapper body and confirm a single unchanged dispatch, opt-in gating, null-slot and depth/stencil/resolve fields. This is not a real Vulkan/device validation. GitHub WCP cross-compilation must succeed before installation.

Retain baseline DXVK/FEX/Turnip/Proton/LSFG, existing CUSTOM_GAME_227938910, 1280x720 and original Engine.ini. Install only an additive unique-version WCP; select using supported UI while idle. Capture genuine Continue gameplay and the same fixed scene. Before enabling this extra env flag, use a supported configuration snapshot/restore path and verify unrelated fields and Engine.ini remain unchanged. Pair diagnostic-enabled observations with diagnostic-enabled comparisons; do not call reduced logging an optimization.

Rank repeated large-area LOAD/STORE passes and resolves by scene. These identify possible tiler bandwidth costs, not proof of redundant stores. Propose a narrow renderer change only after establishing attachment lifetimes; preserve all required stores and hazards. Validate images/device-loss behavior and alternate matched trials before promotion. Current A1 remains baseline-only: 60.7203ms D3D11 Present completion interval, GPU busy 99.917%; no measured improvement.

`python3 tools/ff7r_render_pass_report.py D3D11_LOG --output FRESH_REPORT.json` groups final bound attachment aspects by extent/effective multiview layers and ranks a STORE-area proxy. It discloses orphan records in truncated tails and rejects duplicate process/pass records. Missing attachment records can undercount; use the complete diagnostic log, not a short tail. Proxy totals cannot estimate bytes or shader cost and do not prove stores are redundant.
