#pragma once

#include "../util/config/config.h"
#include "../util/util_env.h"

#include "../vulkan/vulkan_loader.h"

namespace dxvk {

  struct DxvkOptions {
    DxvkOptions() { }
    DxvkOptions(const Config& config);

    /// Enable debug utils
    bool enableDebugUtils = false;

    /// Enable memory defragmentation
    Tristate enableMemoryDefrag = Tristate::Auto;

    /// Number of compiler threads
    /// when using the state cache
    int32_t numCompilerThreads = 0;

    /// Qualcomm/Turnip Adreno 650 policy: auto, disabled, or forced for testing.
    Tristate sd865Profile = Tristate::Auto;

    /// Log selected A650 driver properties and enabled Vulkan features.
    bool sd865Diagnostics = true;

    /// Optional A/B compiler-worker override; 0 = original DXVK behaviour.
    /// dxvk.numCompilerThreads takes precedence over this experimental setting.
    int32_t sd865CompilerThreads = 0;

    /// Interval (present requests) for optional render-pass/counter telemetry.
    /// 0 disables logging; nonzero values are clamped to 60..3600.
    uint32_t sd865StatsInterval = 0u;

    /// Optional per-task compiler timing and queue-depth diagnostics.
    bool sd865CompilerTelemetry = false;

    /// Enable graphics pipeline library
    Tristate enableGraphicsPipelineLibrary = Tristate::Auto;

    /// Enable descriptor heap
    Tristate enableDescriptorHeap = Tristate::Auto;

    /// Enable descriptor buffer
    Tristate enableDescriptorBuffer = Tristate::Auto;

    /// Enable unified image layout path
    bool enableUnifiedImageLayout = true;

    /// Enables pipeline lifetime tracking
    Tristate trackPipelineLifetime = Tristate::Auto;

    /// Shader-related options
    Tristate useRawSsbo = Tristate::Auto;

    /// HUD elements
    std::string hud;

    /// Forces swap chain into MAILBOX (if true)
    /// or FIFO_RELAXED (if false) present mode
    Tristate tearFree = Tristate::Auto;

    /// Enables latency sleep
    Tristate latencySleep = Tristate::Auto;

    /// Latency tolerance, in microseconds
    int32_t latencyTolerance = 0u;

    /// Disable VK_NV_low_latency2. This extension
    /// appears to be all sorts of broken on 32-bit.
    Tristate disableNvLowLatency2 = Tristate::Auto;

    // Hides integrated GPUs if dedicated GPUs are
    // present. May be necessary for some games that
    // incorrectly assume monitor layouts.
    bool hideIntegratedGraphics = false;

    /// Clears all mapped memory to zero.
    bool zeroMappedMemory = false;

    /// Allows full-screen exclusive mode on Windows
    bool allowFse = false;

    /// Whether to enable tiler optimizations
    Tristate tilerMode = Tristate::Auto;

    /// Overrides memory budget for DXVK
    VkDeviceSize maxMemoryBudget = 0u;

    /// Whether to use custom sin/cos approximation
    Tristate lowerSinCos = Tristate::Auto;

    /// Enables implicit resolves that are used to
    /// deal with MSAA-related undefined behaviour.
    bool enableImplicitResolves = true;

    /// Enables NV_raw_access_chains extension on Nvidia
    bool enableNvRawAccessChains = true;

    /// Enables CUDA interop extensions if available
    bool enableNvCudaInterop = true;

    /// Enable present timing features
    bool enablePresentTiming = true;

    /// Enable descriptor update templates
    bool enableDescriptorUpdateTemplates = env::is32BitHostPlatform();

    /// Device name
    std::string deviceFilter;
  };

}
