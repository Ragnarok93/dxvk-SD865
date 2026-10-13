# FF7R: Vulkan 1.3 backport ledger

Baseline: `d82db60d326395d9865eac4cfec9605eb9d3c689`, on
`feature/ff7r-sd865-architecture-20261011`. Target: GameNative, Snapdragon
865 / Adreno 650. Upstream reference: DXVK v3.1.1. This is a selective
backport to 2.7.1, not a complete 3.1.1 implementation.

## Fork survey before implementation

Current sources inspected on 2026-10-13:

| Source | Evidence and decision |
| --- | --- |
| `doitsujin/dxvk` v3.1.1 | Read release ancestry and candidate diffs. Retain 2.7.1 shader/compiler/device requirements; select independent fixes below. |
| `winhub-emu/vegas` `49c2ac40d33651dde81d937194e42844e4f79395` | Inspect README, context and allocator. Draw skipping while compiling and pipeline-bind elision need device correctness evidence; not imported. Its 64 MiB KGSL cap overlaps our prior unsuccessful allocator experiment. |
| `isygold/Vegas-Private` `6b58f71` | Inspect developer feature inventory; governor, bind skipping, integrated FG and GPU persona changes are unsuitable additions to this fixed LSFG/vkBasalt comparison. |
| `Digger1955/dxvk-gplall` `6a0ea56` | MSAA optimization targets devices without shaderInt64; A650 path and FF7R benefit not established. No import. |
| `JustCallMeJade/dxvk-arm64ec` `52fe923ca1496c8e44789b613fab8611dfcb5c4a` | Packaging/architecture alternative, no identified A650-specific patch required for these backports. |
| `Ph42oN/dxvk-gplasync` | Source cloned; async compilation is an alternative requiring separate rendering validation, not a mandatory Vulkan 1.3 replacement. |
| Historical mobile/driver candidates | See `FF7R-A650-TURNIP-DXVK311-COMPATIBILITY-SURVEY.md`. Vulkan version overrides do not implement missing 8-bit storage semantics. |

Discovery used public repository search and source inspection. This is the
identified relevant fork set, not a claim to have reviewed every GitHub fork
or unavailable private repository.

## Applied independent upstream changes

| Upstream commit | Change | Compatibility |
| --- | --- | --- |
| `d92226b6` | Tiler secondary command buffers (previous checkpoint) | Existing Vulkan 1.3 command-buffer path |
| `e11a953a` | Separately lock descriptor-set/pipeline-layout maps | Host synchronization only; pipeline lock precedes layout lock, no recursive layout creation |
| `b1ef9e7c` | Skip fence waits already satisfied | Existing Vulkan 1.2 timeline semaphore query; unsatisfied waits retained |
| `3c6a6ff1` | Preserve imported resource cookies | Host bookkeeping; fixes imported-resource lookup |
| `662b5068` | Omit empty pipeline flags2 structures | Reduces unnecessary maintenance5 pNext use; nonzero flags remain on existing supported extension path |
| `0aea8528` + `64542839` | Handle unavailable display refresh rates without division by zero | Host frame statistics only; regression reproduced SIGFPE, fixed code passes 60/120/fractional/zero-rate tests |

## Deferred or already equivalent

- `fb34f940`, `c46d935c`, `84c34155`: later descriptor allocator has a different lifetime model. 2.7.1 already resets recycled pools in command-list cleanup; do not replace caching without a measured memory/CPU benefit.
- New dxbc-spirv compiler, descriptor heap and mandatory storage8 changes: require substantial shader lowering and conformance work. Keep the functioning legacy compiler rather than spoofing features.
- `cc418519`: concurrent optimized variants require adapting the key/container model and testing concurrent publication; not blindly cherry-picked.
- Synchronization/render-pass changes dependent on the 3.x access tracker are not imported piecemeal.

## Validation and benchmark contract

Each retained change must pass cross-compilation and existing tests. Device
startup, image correctness and frame-time improvements remain unverified
until measured on the S20+. No speedup is claimed from source review alone.

Checkpoint `bc93bd59`: six upstream commits applied, existing 48 tests and
one compiled refresh arithmetic regression pass. Dedicated WCP CI now
watches all source changes and runs the full test suite: the previous narrow
path filter omitted DXVK core backports, so it could silently leave the
benchmark artifact stale. Source and shader compiler requirements unchanged.

Keep LSFG and vkBasalt enabled in the container between runs. LSFG frame
generation is disabled in-game. Keep textures Low (the user's established
stable setting), resolution, save/scene, FEX build, thermals and cache state
fixed. Compare at least three matched warm-cache trials against `d82db60`;
record real-frame median, p95/p99, crashes and visible corruption. Separate
DXVK and Turnip trials. Retain experiments as candidates until that gate.
