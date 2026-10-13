# FFVII Remake — DXVK tiler render-area backport

**Source:** upstream DXVK commit [`d92226b6`](https://github.com/doitsujin/dxvk/commit/d92226b6a9e5ac7d9e9f00999b0feb54c9e1987e), titled “Use secondary command buffers for all render passes on tilers.”

## Change

The DXVK 2.7.1 branch already marks Turnip and Qualcomm proprietary drivers as tilers through `preferRenderPassOps`. This backport uses that existing capability hint to select a secondary command buffer for every tiler render pass, including a single-color, single-sample pass. DXVK can then trim the render area for trivial passes. No Vulkan extensions, feature bits, API version, or DXVK device requirements change.

This remains on the working DXVK 2.7.1 base. DXVK 3.1.1 itself still cannot initialize with the captured S20+ Mr. Purple T30 feature set because `storageBuffer8BitAccess` is reported false. This change does not bypass that requirement or claim 3.1.1 compatibility.

## Review of Adreno-specific alternatives

The surveyed Star Engine / Vegas patch set is based on DXVK 2.7.1 and includes experimental draw skipping, pipeline-bind skipping, forced mid-render submissions, and async paths that may drop draws. Those changes lack correctness evidence for FFVII Remake and are not included. The selected upstream hunk is small, guarded by DXVK’s existing tiler capability hint, and does not change behavior on drivers without that hint.

## Validation status

- [x] Exact upstream hunk inspected and adapted to the 2.7.1 source context.
- [x] `git diff --check` passes.
- [ ] DXVK 32-bit and 64-bit build CI.
- [ ] Install and smoke-test on the S20+ Turnip/T30 path.
- [ ] Compare against the unchanged 2.7.1 control in the same FFVII Remake scene: at least three matched runs, shader cache warmed equally, LSFG and vkBasalt enabled in-container, LSFG frame generation disabled in-game; record median and p95/p99 real-frame times plus visual correctness.

The change may add CPU command-buffer overhead on trivial passes. Keep it only if the matched GameNative test shows no correctness regression and improves or preserves FFVII Remake frame pacing.
