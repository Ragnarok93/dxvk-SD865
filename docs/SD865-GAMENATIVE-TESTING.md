# Testing DXVK-SD865 in our GameNative fork

Updated 2026-10-09. Target: Galaxy S20+ (Snapdragon 865 / Adreno 650), the latest A650-compatible Turnip drivers and optimized forks, and [Ragnarok93/GameNative](https://github.com/Ragnarok93/GameNative).

**Goal:** Verify DXVK-SD865 loads through GameNative, collect rendering and shader-worker evidence, and isolate any improvement from changes to drivers, translator, LSFG, temperature or game settings. Current SD865 changes are experimental; **no measured gains are claimed**.

## Part A — Download a GameNative-ready build

1. Open [DXVK-SD865 Actions](https://github.com/Ragnarok93/dxvk-SD865/actions), select **GameNative DXVK WCP**, and choose a **successful** run on `feature/sd865-foundation-20261009` (or the current release branch).
2. Download the **single** `gamenative-dxvk-<full-commit-sha>` GitHub Actions artifact. It contains **one** installable `dxvk-sd865-<short-commit-sha>.wcp`; this build no longer publishes raw DLLs, Linux/native tarballs, merged archives or MSVC build outputs.
3. GitHub Actions automatically wraps artifacts in ZIP. **Extract the inner `.wcp`** before importing it into GameNative; the outer ZIP isn't an installable WCP.
4. The package contains Windows **x64 and x32 PE DXVK DLLs**, **not native ARM64EC DXVK DLLs**. Confirm the selected GameNative Proton/FEX loader uses them.

### Manual WCP creation, if the Actions packaging job is unavailable

For local-only packaging, first compile with `./package-release.sh sd865-local build --no-package` using a matching MinGW toolchain. This creates **intermediate** `build/dxvk-sd865-local/x64/` and `x32/` DLL directories (not published CI downloads). On Linux or a Python-capable Android environment with `zstd`, run:

```sh
python3 tools/package_gamenative_wcp.py \
  --input ./build/dxvk-sd865-local \
  --output ./dxvk-sd865-test.wcp \
  --version-name sd865-manual-test
zstd -t ./dxvk-sd865-test.wcp
zstd -dc ./dxvk-sd865-test.wcp | tar -tf - | head
```

The decompressed archive should contain a root-level `profile.json` plus `x64/` and `x32/` DLLs. The CI download provides only this `.wcp` payload. GameNative's importer expects a **tar.xz/tar.zst WCP content profile**, not a renamed ZIP or normal DXVK release tarball. Our packager generates the `DXVK` profile and uses only GameNative's trusted `system32`/`syswow64` DLL targets.

## Part B — Install and select DXVK-SD865 in GameNative

1. Open your GameNative APK, navigate to **Settings → Contents Manager → Import from device**, and select the extracted `.wcp`.
2. Confirm content type **DXVK** and a version starting `sd865-`; allow installation to complete. If prompted about untrusted files, stop and inspect the archive rather than blindly approving unexpected targets. The bundled packager uses the exact allowed DXVK DLL list.
3. Open the game's **configuration → Graphics** tab, set the active Bionic graphics driver to a known-working **Wrapper** with **Use Adrenotools Turnip** enabled.
4. In **Graphics Driver Version**, select a **Turnip build that supports Adreno 650**. Do not use packages labeled Gen8/A8xx only. Record the *exact* selected driver.
5. Set **DX Wrapper = DXVK**. In **DXVK Version**, explicitly choose `sd865-<sha>`. Save, close settings, and restart the game. GameNative's current Adreno 6xx default is `1.11.1-sarek`, so never assume the test build was selected automatically.
6. Keep DXVK tests on **D3D9/10/11**. VKD3D / D3D12 benchmarks evaluate a different translation layer and are not valid DXVK A/B results.

If the version is missing, return to **Settings → Contents Manager → DXVK**, check installed contents, and restart GameNative before selecting it again. If the selected Proton ARM64EC/Wine combination does not load the x64/x32 component, document that separately as a loader/architecture issue.

**Source references:** [Contents Manager](https://github.com/Ragnarok93/GameNative/blob/master/app/src/main/java/app/gamenative/ui/screen/settings/ContentsManagerDialog.kt), [Graphics tab](https://github.com/Ragnarok93/GameNative/blob/master/app/src/main/java/app/gamenative/ui/component/dialog/GraphicsTab.kt), [component profile format](https://github.com/Ragnarok93/GameNative/blob/master/app/src/main/java/com/winlator/contents/ContentProfile.java).

## Part C — Enable and VERIFY SD865 configuration and logs

GameNative's [DXVKHelper.java](https://github.com/Ragnarok93/GameNative/blob/master/app/src/main/java/com/winlator/core/DXVKHelper.java) currently sets `DXVK_LOG_LEVEL=none` and writes both `DXVK_CONFIG` and `DXVK_CONFIG_FILE` at launch. The referenced file is under the selected imagefs's `/home/xuser/.config/dxvk.conf`. This means manually setting `DXVK_LOG_LEVEL=info` in a game's Environment tab **may be overridden**.

If you can access the GameNative imagefs config directory (through your fork's container terminal/file manager), use:

```ini
dxvk.sd865Profile = Auto
dxvk.sd865Diagnostics = True
dxvk.sd865CompilerThreads = 0
dxvk.sd865StatsInterval = 300
dxvk.sd865CompilerTelemetry = True
```

**Recommended fork-specific test hook:** In `DXVKHelper.setEnvVars()` add a *testing-only* conditional gated by a custom environment variable, e.g. `GN_SD865_TESTING=1`. After GameNative's existing DXVK environment assignments, set `DXVK_LOG_LEVEL=info` and create/update `imageFs.config_path + "/dxvk.conf"` with the five lines above; take the worker setting from another Environment variable `GN_SD865_WORKERS` (default `0`). This lets you switch 0/2/3/4 worker counts on the same GameNative build. Preserve GameNative's other DXVK configuration options: don't replace its entire configuration with an unrelated text blob.

### Copyable GameNative test hook (optional, but recommended)

If you can build the GameNative fork, add this block **at the end of** `DXVKHelper.setEnvVars()`, after its existing `envVars.put("DXVK_CONFIG", content);`. It uses fully qualified Java class names, so no extra imports are required. This affects only a game profile with `GN_SD865_TESTING=1`:

```java
if ("1".equals(envVars.get("GN_SD865_TESTING"))) {
    String requestedWorkers = envVars.get("GN_SD865_WORKERS");
    String workers = requestedWorkers.matches("[0-8]") ? requestedWorkers : "0";
    boolean profile = "1".equals(envVars.get("GN_SD865_TELEMETRY"));

    String sdConfig =
        "dxvk.sd865Profile = Auto\n" +
        "dxvk.sd865Diagnostics = True\n" +
        "dxvk.sd865CompilerThreads = " + workers + "\n" +
        "dxvk.sd865StatsInterval = " + (profile ? "300" : "0") + "\n" +
        "dxvk.sd865CompilerTelemetry = " + (profile ? "True" : "False") + "\n";

    java.io.File testConf = new java.io.File(
        imageFs.config_path, "dxvk-sd865-test.conf");
    if (testConf.getParentFile().mkdirs() || testConf.getParentFile().isDirectory()) {
        try (java.io.FileOutputStream out = new java.io.FileOutputStream(testConf)) {
            out.write(sdConfig.getBytes(java.nio.charset.StandardCharsets.UTF_8));
            envVars.put("DXVK_CONFIG_FILE", testConf.getAbsolutePath());
        } catch (java.io.IOException e) {
            android.util.Log.e("DXVK-SD865", "Failed to write test config", e);
        }
    }

    if ("1".equals(envVars.get("GN_SD865_LOG")))
        envVars.put("DXVK_LOG_LEVEL", "info");
}
```

In **GameNative → game configuration → Environment**, add `GN_SD865_TESTING=1`, `GN_SD865_WORKERS=0`, `GN_SD865_TELEMETRY=1`, and `GN_SD865_LOG=1` for the initial capability check. Change only `GN_SD865_WORKERS` to `2`, `3` or `4` for follow-up tests. For **unprofiled FPS runs**, change `GN_SD865_TELEMETRY=0` and `GN_SD865_LOG=0`; use a separate logged startup check to verify the component. Disable the test hook entirely by setting `GN_SD865_TESTING=0`.

This uses a dedicated `dxvk-sd865-test.conf` instead of overwriting the user's existing `dxvk.conf`, and retains GameNative's regular `DXVK_CONFIG` settings. The test-only file can stay on disk without affecting sessions where the test flag is disabled.

**Never trust just the GUI toggle.** On startup, verify the effective log contains:

```text
DXVK: 3.1.1
DXVK-SD865: GPU=...
DXVK-SD865 enabled Vulkan features: ...
DXVK-SD865 counters over 300 present requests: ...
```

With a nonzero worker override also expect `DXVK-SD865: experimental compiler worker count=...`. Check the `Effective configuration` block and `Found config file:` where present. The log marker plus the selected package proves the experiment is running; the version string `3.1.1` by itself does not distinguish upstream from this fork.

DXVK logs may be written to the current game working directory or to a location configured with `DXVK_LOG_PATH`. GameNative's crash diagnostics may not automatically export these DXVK files; confirm that the exported logs actually contain `DXVK-SD865` lines. If not, use an accessible DXVK log directory or a small GameNative test-only export hook. Do not assume Android logcat alone captures file-based DXVK logging.

## Part D — Freeze all other variables

For the first comparison use one fixed GameNative APK SHA, one Wine/Proton version, one FEX/Box64 preset, and one **exact A650 Turnip package**. Use the same display renderer, present mode, refresh rate, resolution, graphical effects, framerate cap, shader-cache condition and thermal/power state.

**Turn off Legacy LSFG, Native LSFG, adaptive frame generation and any post-DXVK generated-frame FPS displays** for the first benchmark series. Frame generation changes what reaches the screen, not the number of original game frames produced by DXVK. Test LSFG separately after identifying a stable DXVK baseline. Avoid changing GPU-driver resource modes (GMEM/SYSMEM), descriptor toggles, Vulkan extensions or unofficial async shader skipping during these comparisons.

Record `driverID`, `vendorID`, `deviceID`, Vulkan API, Turnip source/fork/package, GameNative commit, translator build, selected component and game mode. A newer Mesa/Vulkan version is **not** proof that every required Vulkan feature works or that the driver is faster.

## Part E — Run the benchmark matrix

**Game 1: Kingdom Hearts III (PC).** Prefer a repeatable save and traversal/battle scene in its **D3D11 path**. Start with **720p** and a single fixed quality preset; note shaders/loading separately. Capture a consistent movement/camera sequence.

**Game 2: Crisis Core – Final Fantasy VII Reunion (PC).** Start at **1152×648**, textures High, shadows Low, AA Low, AO Off, in the same combat or traversal scene. Add 1280×720 after startup/scene stability is demonstrated. Target **30 real rendered FPS**, no frame generation during the core test. Confirm it is actually using D3D11, not VKD3D.

| Test | DXVK | SD865 workers | Purpose |
| --- | --- | --- | --- |
| Compatibility check | GameNative working `1.11.1-sarek` | n/a | Game and launcher sanity only |
| **C1: actual control** | **Upstream DXVK 3.1.1** built with same toolchain | upstream | Apples-to-apples baseline |
| **S0: baseline** | DXVK-SD865 same base | `0` | Detect changes/regressions |
| S2 | Same DXVK-SD865 | `2` | CPU/compile contention experiment |
| S3 | Same DXVK-SD865 | `3` | Alternative worker count |
| S4 | Same DXVK-SD865 | `4` | Alternative worker count |
| P: diagnosis | Best stable candidate | unchanged | Telemetry ON, **not an FPS score** |
| D: driver variation | C1, S0, winning S* | same per pair | Repeat using alternative A650 Turnip fork |

**Important:** Sarek 1.11.1 and DXVK 3.1.1 differ fundamentally. Their comparison is useful for compatibility but **cannot prove SD865-specific changes are faster**. Compile/package matching upstream 3.1.1 for C1 if it isn't already available.

For each test, use the same scene **five times**. After a consistent warm-up (e.g. 15 seconds), capture 60–120 seconds of real gameplay. Alternate control/candidate order where possible to limit heat/cache bias. Separate **cold shader cache** from **warm cache** runs. Restart the game between DLL/config changes.

Use `dxvk.sd865CompilerThreads = 0` to preserve the upstream worker policy. GameNative's `dxvk.numCompilerThreads` setting, if already configured, takes precedence. To reduce measurement overhead, disable both profiling options (`sd865StatsInterval = 0` and `sd865CompilerTelemetry = False`) for benchmark FPS runs and enable them only during the diagnostic pass.

## Part F — Collect results

Copy one row per timed run (then compute median / confidence range across runs):

| Test ID | Turnip package | GameNative / DXVK SHA | Workers | Cache | Avg FPS | 1% low | p99 ms | Passes/present | Barriers/present | Visual issues |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| KH3-C1-01 | exact name | upstream SHA | upstream | warm | — | — | — | — | — | — |
| KH3-S0-01 | same | SD865 SHA | 0 | warm | — | — | — | — | — | — |
| KH3-S3-01 | same | SD865 SHA | 3 | warm | — | — | — | — | — | — |
| CC-S0-01 | same | SD865 SHA | 0 | warm | — | — | — | — | — | — |

For enabled SD865 logs, run the existing parser on any Python-capable device:

```sh
python3 tools/sd865_telemetry.py dxvk.log
python3 tools/sd865_telemetry.py dxvk.log --json > sd865-results.json
```

The output includes **render passes/present request, barriers/present request, draws, submits, GPU/CS CPU-wait counters**, and shader compilation queue/compile time summaries. **Present requests are not physical frames on screen**; compiler CPU-work totals can overlap between threads; neither the parser nor the DXVK counters measures true GMEM bandwidth or p99 frametime. Capture FPS, 1% low, p95/p99 and temperature using independent tooling where available, and record them separately.

Save the **complete startup log**, at least one full diagnostic log plus its JSON output for each game/driver, benchmark tables and identical-scene screenshots when graphical errors occur.

## Part G — Troubleshoot and stop conditions

| Symptom | First check |
| --- | --- |
| `Profile not found` during WCP import | Used GitHub artifact ZIP instead of inner tar.zst `.wcp`; missing root `profile.json` |
| `Content incomplete` | Missing x32/x64 DLLs or profile source paths; regenerate with provided packager |
| `Content already exists` | Same `versionName` previously imported; remove the old profile or change version name |
| New version absent in UI | Settings → Contents Manager → DXVK; restart configuration view/GameNative |
| No `DXVK-SD865` line | Verify selected DLL/component, D3D11 path, effective `DXVK_LOG_LEVEL` and log export |
| Profile says disabled | Check actual Mesa Turnip Vulkan `driverID` / Qualcomm `vendorID` / GPU name; do not blindly force |
| Vulkan 1.3 / missing feature failure | Capture the first actual incompatibility; try a current verified A650 Turnip build; never spoof feature flags |
| More workers cause stutter | Revert to 0/2; CPU contention in FEX can exceed the benefit |
| GPU device loss, crash or Android reboot | Stop that driver test, save logs and identify fork/UBWC readback behavior; don't globally disable UBWC |
| Generated FPS differs from measured rendering FPS | Disable LSFG until normal DXVK correctness/frametime tests pass |

## Done: evidence for the next optimization pass

Keep the run with **lowest repeatable real-game frametime and correct visuals**, not simply highest synthetic/LSFG FPS. A candidate should not be selected if it produces texture corruption, device loss, missing objects or severe p99 spikes.

Send back these four items for analysis: **(1) DXVK startup log**, **(2) parser JSON and raw telemetry**, **(3) results table across worker settings**, and **(4) any visual-error screenshots**. I can then use the measured symptoms to prioritize shader scheduling, render-pass/GMEM optimization, or memory allocation work rather than guessing.

Related documents: [SD865 profile](./SD865-PROFILE.md) · [Optimization roadmap](./SD865-OPTIMIZATION-ROADMAP.md) · [WCP packager](../tools/package_gamenative_wcp.py) · [Telemetry parser](../tools/sd865_telemetry.py).
