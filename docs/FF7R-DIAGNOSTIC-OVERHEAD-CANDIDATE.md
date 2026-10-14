# Diagnostic overhead candidate (not a GPU/rendering optimization claim)

Parent:749729333e9b7cfddc427c8fc57cb24b7cb5f3ce, the installed 2.7.1-based
SD865 fork. Existing 3.1.1 backports, capabilities, shaders, pool configuration,
and Vulkan synchronization remain unchanged. No stock/ARM64EC DXVK substitution.

Ff7rTimingCounter now reports first sample and every1024 samples rather than64.
All samples, sums, maxima and threshold counts remain captured. Optional64
interval retains old cadence; invalid non-power-of-two intervals fall back1024.
A mask avoids adding runtime division in this diagnostic hot path. Native test
4096samples at12000us: baseline65 reports, candidate5 reports, rollback65;
all count4096, mean12000us, over10ms4096. Concurrent accounting test passes.

This reduces reporting opportunities by60/65 (92.3%) in that probe. It does not
measure logger CPU savings, prove native/FEX speedup, or predict FPS. Clock reads
and atomic counter updates remain; final non-boundary samples do not get a new
flush. Sparse log cadence is a trade-off, with coarser observation timing.

Experimental artifact-only CI uses the exact branch/commit, pins ancestry,
stamps identity and builds x32/x64 compatible PE/WCP. Automatic prerelease
publication is disabled. Do not install/select over the baseline automatically.
Next compare baseline and candidate with same existing container, Engine.ini,
scene/input/cache state/FEX/Turnip/Proton/LSFG; log thermal state and actual
presentation coverage, and confirm no device loss or visual regression. No
stable promotion before those measured comparisons. GPU waits are not removed.
