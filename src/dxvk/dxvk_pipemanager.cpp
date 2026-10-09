#include <optional>

#include "dxvk_device.h"
#include "dxvk_pipemanager.h"
#include "dxvk_sd865.h"

namespace dxvk {

  // C++17-compatible relaxed atomic peak tracker. Only exercised when
  // opt-in profiling is enabled; does not affect compilation decisions.
  static void updateSd865Peak(std::atomic<uint64_t>& peak, uint64_t value) {
    uint64_t old = peak.load(std::memory_order_relaxed);
    while (old < value && !peak.compare_exchange_weak(
             old, value, std::memory_order_relaxed)) { }
  }
  
  DxvkPipelineWorkers::DxvkPipelineWorkers(
          DxvkDevice*                     device)
  : m_device(device),
    m_sd865TelemetryEnabled(device->isSd865ProfileActive() && device->config().sd865CompilerTelemetry) {

  }


  DxvkPipelineWorkers::~DxvkPipelineWorkers() {
    this->stopWorkers();
  }


  void DxvkPipelineWorkers::compilePipelineLibrary(
          DxvkShaderPipelineLibrary*      library,
          DxvkPipelinePriority            priority) {
    std::unique_lock lock(m_lock);
    this->startWorkers();

    m_tasksTotal += 1;

    m_buckets[uint32_t(priority)].queue.emplace(library);
    if (m_sd865TelemetryEnabled) {
      m_buckets[uint32_t(priority)].queue.back().queuedAt = std::chrono::steady_clock::now();
      uint64_t queued = 0u;
      for (const auto& bucket : m_buckets)
        queued += bucket.queue.size();
      updateSd865Peak(m_sd865PeakPending, queued);
    }
    notifyWorkers(priority);
  }


  void DxvkPipelineWorkers::compileGraphicsPipeline(
          DxvkGraphicsPipeline*           pipeline,
    const DxvkGraphicsPipelineStateInfo&  state,
          DxvkPipelinePriority            priority) {
    std::unique_lock lock(m_lock);
    this->startWorkers();

    pipeline->acquirePipeline();
    m_tasksTotal += 1;

    m_buckets[uint32_t(priority)].queue.emplace(pipeline, state);
    if (m_sd865TelemetryEnabled) {
      m_buckets[uint32_t(priority)].queue.back().queuedAt = std::chrono::steady_clock::now();
      uint64_t queued = 0u;
      for (const auto& bucket : m_buckets)
        queued += bucket.queue.size();
      updateSd865Peak(m_sd865PeakPending, queued);
    }
    notifyWorkers(priority);
  }


  void DxvkPipelineWorkers::stopWorkers() {
    { std::unique_lock lock(m_lock);

      if (!m_workersRunning)
        return;

      m_workersRunning = false;

      for (uint32_t i = 0; i < m_buckets.size(); i++)
        m_buckets[i].cond.notify_all();
    }

    for (auto& worker : m_workers)
      worker.join();

    m_workers.clear();

    if (m_sd865TelemetryEnabled) {
      uint64_t count = m_tasksCompleted.load(std::memory_order_relaxed);
      Logger::info(str::format(
        "DXVK-SD865 compiler totals: completed=", count,
        " scheduled=", m_tasksTotal.load(std::memory_order_relaxed),
        " queuedWaitUs=", m_sd865WaitUs.load(std::memory_order_relaxed),
        " compileWorkUs=", m_sd865WorkUs.load(std::memory_order_relaxed),
        " peakQueueWaitUs=", m_sd865PeakWaitUs.load(std::memory_order_relaxed),
        " peakCompileUs=", m_sd865PeakWorkUs.load(std::memory_order_relaxed),
        " peakPending=", m_sd865PeakPending.load(std::memory_order_relaxed)));
    }
  }


  void DxvkPipelineWorkers::notifyWorkers(DxvkPipelinePriority priority) {
    uint32_t index = uint32_t(priority);

    // If any workers are idle in a suitable set, notify the corresponding
    // condition variable. If all workers are busy anyway, we know that the
    // job is going to be picked up at some point anyway.
    for (uint32_t i = index; i < m_buckets.size(); i++) {
      if (m_buckets[i].idleWorkers) {
        m_buckets[i].cond.notify_one();
        break;
      }
    }
  }


  void DxvkPipelineWorkers::startWorkers() {
    if (!std::exchange(m_workersRunning, true)) {
      // Determine number of available CPU cores, and clamp to a useful
      // range. DXVK is not tested on extremely high core counts, and
      // parallelism may be limited past a certain point.
      uint32_t coreCount = sd865::chooseCompilerWorkerCount(
        dxvk::thread::hardware_concurrency(),
        m_device->config().numCompilerThreads,
        m_device->config().sd865CompilerThreads,
        m_device->isSd865ProfileActive());

      // Manual upstream override wins. SD865-specific worker tuning is opt-in.
      if (m_device->isSd865ProfileActive()
       && m_device->config().numCompilerThreads <= 0
       && m_device->config().sd865CompilerThreads > 0)
        Logger::info(str::format("DXVK-SD865: experimental compiler worker count=", coreCount));

      // Reduce worker count on 32-bit to save adderss space
      uint32_t workerCount = coreCount;

      if (env::is32BitHostPlatform())
        workerCount = std::min(workerCount, 8u);

      // Number of workers that can process pipeline pipelines with normal
      // priority. Any other workers can only build high-priority pipelines.
      // Base this on the available core count, not the worker count, since
      // that is what determines the impact of having multiple threads do
      // heavy CPU work.
      uint32_t npWorkerCount = std::clamp(((coreCount - 1) * 5) / 7, 1u, workerCount);
      uint32_t lpWorkerCount = std::clamp(((coreCount - 1) * 2) / 7, 1u, workerCount);

      m_workers.reserve(workerCount);

      for (size_t i = 0; i < workerCount; i++) {
        DxvkPipelinePriority priority = DxvkPipelinePriority::Normal;

        if (i >= npWorkerCount)
          priority = DxvkPipelinePriority::High;
        else if (i < lpWorkerCount)
          priority = DxvkPipelinePriority::Low;

        auto& worker = m_workers.emplace_back([this, priority] {
          runWorker(priority);
        });
        
        worker.set_priority(ThreadPriority::Lowest);
      }

      Logger::info(str::format("DXVK: Using ", workerCount, " compiler threads"));
    }
  }


  void DxvkPipelineWorkers::runWorker(DxvkPipelinePriority maxPriority) {
    static const std::array<char, 3> suffixes = { 'h', 'n', 'l' };

    const uint32_t maxPriorityIndex = uint32_t(maxPriority);
    env::setThreadName(str::format("dxvk-shader-", suffixes.at(maxPriorityIndex)));

    while (true) {
      PipelineEntry entry;

      { std::unique_lock lock(m_lock);
        auto& bucket = m_buckets[maxPriorityIndex];

        bucket.idleWorkers += 1;
        bucket.cond.wait(lock, [this, maxPriorityIndex, &entry] {
          // Attempt to fetch a work item from the
          // highest-priority queue that is not empty
          for (uint32_t i = 0; i <= maxPriorityIndex; i++) {
            if (!m_buckets[i].queue.empty()) {
              entry = m_buckets[i].queue.front();
              m_buckets[i].queue.pop();
              return true;
            }
          }

          return !m_workersRunning;
        });

        bucket.idleWorkers -= 1;

        // Skip pending work, exiting early is
        // more important in this case.
        if (!m_workersRunning)
          break;
      }

      const auto begin = m_sd865TelemetryEnabled
        ? std::chrono::steady_clock::now()
        : std::chrono::steady_clock::time_point();

      if (entry.pipelineLibrary) {
        entry.pipelineLibrary->compilePipeline();
      } else if (entry.graphicsPipeline) {
        entry.graphicsPipeline->compilePipeline(entry.graphicsState);
        entry.graphicsPipeline->releasePipeline();
      }

      if (m_sd865TelemetryEnabled) {
        const auto finish = std::chrono::steady_clock::now();
        const uint64_t workUs = std::chrono::duration_cast<std::chrono::microseconds>(
          finish - begin).count();
        const uint64_t waitUs = std::chrono::duration_cast<std::chrono::microseconds>(
          begin - entry.queuedAt).count();

        m_sd865WorkUs.fetch_add(workUs, std::memory_order_relaxed);
        m_sd865WaitUs.fetch_add(waitUs, std::memory_order_relaxed);
        updateSd865Peak(m_sd865PeakWorkUs, workUs);
        updateSd865Peak(m_sd865PeakWaitUs, waitUs);
      }

      uint64_t completed = m_tasksCompleted.fetch_add(1, std::memory_order_relaxed) + 1;

      // Summary every 128 completed tasks: bounded log volume, no per-task I/O.
      if (m_sd865TelemetryEnabled && !(completed % 128u)) {
        Logger::info(str::format(
          "DXVK-SD865 compiler sample: tasks=", completed,
          " total=", m_tasksTotal.load(std::memory_order_relaxed),
          " avgQueueWaitUs=", m_sd865WaitUs.load(std::memory_order_relaxed) / completed,
          " avgCompileUs=", m_sd865WorkUs.load(std::memory_order_relaxed) / completed,
          " maxQueueWaitUs=", m_sd865PeakWaitUs.load(std::memory_order_relaxed),
          " maxCompileUs=", m_sd865PeakWorkUs.load(std::memory_order_relaxed),
          " peakPending=", m_sd865PeakPending.load(std::memory_order_relaxed)));
      }
    }
  }


  DxvkPipelineManager::DxvkPipelineManager(
          DxvkDevice*         device)
  : m_device    (device),
    m_workers   (device) {
    Logger::info(str::format("Graphics pipeline libraries ",
      (m_device->canUseGraphicsPipelineLibrary() ? "supported" : "not supported")));

    if (!m_device->canUseDescriptorHeap())
      m_specLayout = createSpecDataSetLayout();
  }
  
  
  DxvkPipelineManager::~DxvkPipelineManager() {
    auto vk = m_device->vkd();

    if (!m_device->canUseDescriptorHeap())
      vk->vkDestroyDescriptorSetLayout(vk->device(), m_specLayout, nullptr);
  }
  
  
  DxvkComputePipeline* DxvkPipelineManager::createComputePipeline(
    const DxvkComputePipelineShaders& shaders) {
    if (shaders.cs == nullptr)
      return nullptr;
    
    std::lock_guard<dxvk::mutex> lock(m_pipelineMutex);
    
    auto pair = m_computePipelines.find(shaders);
    if (pair != m_computePipelines.end())
      return &pair->second;

    DxvkShaderPipelineLibraryKey key;
    key.addShader(shaders.cs);

    auto library = findPipelineLibraryLocked(key);

    auto iter = m_computePipelines.emplace(
      std::piecewise_construct,
      std::tuple(shaders),
      std::tuple(m_device, this, shaders, library));
    return &iter.first->second;
  }
  
  
  DxvkGraphicsPipeline* DxvkPipelineManager::createGraphicsPipeline(
    const DxvkGraphicsPipelineShaders& shaders) {
    if (shaders.vs == nullptr)
      return nullptr;
    
    std::lock_guard<dxvk::mutex> lock(m_pipelineMutex);

    auto pair = m_graphicsPipelines.find(shaders);
    if (pair != m_graphicsPipelines.end())
      return &pair->second;

    DxvkShaderPipelineLibraryKey vsKey;
    vsKey.addShader(shaders.vs);

    if (shaders.tcs) vsKey.addShader(shaders.tcs);
    if (shaders.tes) vsKey.addShader(shaders.tes);
    if (shaders.gs) vsKey.addShader(shaders.gs);

    DxvkShaderPipelineLibrary* vsLibrary = findPipelineLibraryLocked(vsKey);

    if (!vsLibrary) {
      // If multiple shader stages are participating, create a
      // pipeline library so that it can potentially be reused.
      // Don't dispatch the pipeline library to a worker thread
      // since it should be compiled on demand anyway.
      vsLibrary = createPipelineLibraryLocked(vsKey);
    }

    DxvkShaderPipelineLibraryKey fsKey;

    if (shaders.fs)
      fsKey.addShader(shaders.fs);

    DxvkShaderPipelineLibrary* fsLibrary = findPipelineLibraryLocked(fsKey);

    auto iter = m_graphicsPipelines.emplace(
      std::piecewise_construct,
      std::tuple(shaders),
      std::tuple(m_device, this, shaders, vsLibrary, fsLibrary));
    return &iter.first->second;
  }

  
  DxvkShaderPipelineLibrary* DxvkPipelineManager::createShaderPipelineLibrary(
    const DxvkShaderPipelineLibraryKey& key) {
    std::lock_guard<dxvk::mutex> lock(m_pipelineMutex);
    return createPipelineLibraryLocked(key);
  }


  DxvkGraphicsPipelineVertexInputLibrary* DxvkPipelineManager::createVertexInputLibrary(
    const DxvkGraphicsPipelineVertexInputState& state) {
    std::lock_guard<dxvk::mutex> lock(m_pipelineMutex);

    auto pair = m_vertexInputLibraries.find(state);
    if (pair != m_vertexInputLibraries.end())
      return &pair->second;

    auto iter = m_vertexInputLibraries.emplace(
      std::piecewise_construct,
      std::tuple(state),
      std::tuple(m_device, state));
    return &iter.first->second;
  }


  DxvkGraphicsPipelineFragmentOutputLibrary* DxvkPipelineManager::createFragmentOutputLibrary(
    const DxvkGraphicsPipelineFragmentOutputState& state) {
    std::lock_guard<dxvk::mutex> lock(m_pipelineMutex);

    auto pair = m_fragmentOutputLibraries.find(state);
    if (pair != m_fragmentOutputLibraries.end())
      return &pair->second;

    auto iter = m_fragmentOutputLibraries.emplace(
      std::piecewise_construct,
      std::tuple(state),
      std::tuple(m_device, state));
    return &iter.first->second;
  }
  
  
  void DxvkPipelineManager::registerShader(
    const Rc<DxvkShader>&         shader) {
    DxvkShaderPipelineLibraryKey key;
    key.addShader(shader);

    auto library = createShaderPipelineLibrary(key);
    m_workers.compilePipelineLibrary(library, DxvkPipelinePriority::Normal);
  }


  void DxvkPipelineManager::requestCompileShader(
    const Rc<DxvkShader>&         shader) {
    // Notify immediately so that this only gets called
    // once, even if compilation does ot start immediately
    if (!shader->notifyCompile())
      return;

    // Dispatch high-priority compile job
    DxvkShaderPipelineLibraryKey key;
    key.addShader(shader);

    auto library = findPipelineLibrary(key);

    if (library)
      m_workers.compilePipelineLibrary(library, DxvkPipelinePriority::High);
  }


  DxvkPipelineCount DxvkPipelineManager::getPipelineCount() const {
    DxvkPipelineCount result;
    result.numGraphicsPipelines = m_stats.numGraphicsPipelines.load();
    result.numGraphicsLibraries = m_stats.numGraphicsLibraries.load();
    result.numComputePipelines  = m_stats.numComputePipelines.load();
    return result;
  }


  void DxvkPipelineManager::stopWorkerThreads() {
    m_workers.stopWorkers();
  }


  const DxvkDescriptorSetLayout* DxvkPipelineManager::createDescriptorSetLayout(
    const DxvkDescriptorSetLayoutKey& key) {
    std::lock_guard<dxvk::mutex> lock(m_layoutMutex);

    auto pair = m_descriptorSetLayouts.find(key);
    if (pair != m_descriptorSetLayouts.end())
      return &pair->second;

    auto iter = m_descriptorSetLayouts.emplace(
      std::piecewise_construct,
      std::tuple(key),
      std::tuple(m_device, key));
    return &iter.first->second;
  }


  const DxvkPipelineLayout* DxvkPipelineManager::createPipelineLayout(
    const DxvkPipelineLayoutKey& key) {
    std::lock_guard<dxvk::mutex> lock(m_layoutMutex);

    auto pair = m_pipelineLayouts.find(key);
    if (pair != m_pipelineLayouts.end())
      return &pair->second;

    auto iter = m_pipelineLayouts.emplace(
      std::piecewise_construct,
      std::tuple(key),
      std::tuple(m_device, key));
    return &iter.first->second;
  }


  DxvkShaderPipelineLibrary* DxvkPipelineManager::createPipelineLibraryLocked(
    const DxvkShaderPipelineLibraryKey& key) {
    auto iter = m_shaderLibraries.emplace(
      std::piecewise_construct,
      std::tuple(key),
      std::tuple(m_device, this, key));
    return &iter.first->second;
  }


  DxvkShaderPipelineLibrary* DxvkPipelineManager::findPipelineLibrary(
    const DxvkShaderPipelineLibraryKey& key) {
    std::lock_guard<dxvk::mutex> lock(m_pipelineMutex);
    return findPipelineLibraryLocked(key);
  }


  DxvkShaderPipelineLibrary* DxvkPipelineManager::findPipelineLibraryLocked(
    const DxvkShaderPipelineLibraryKey& key) {
    auto pair = m_shaderLibraries.find(key);

    if (pair != m_shaderLibraries.end())
      return &pair->second;

    return createPipelineLibraryLocked(key);
  }


  VkDescriptorSetLayout DxvkPipelineManager::createSpecDataSetLayout() {
    auto vk = m_device->vkd();

    VkDescriptorSetLayoutBinding binding = {};
    binding.stageFlags = VK_SHADER_STAGE_ALL_GRAPHICS;

    if (m_device->canUseDescriptorBuffer()) {
      binding.descriptorType = VK_DESCRIPTOR_TYPE_INLINE_UNIFORM_BLOCK;
      binding.descriptorCount = sizeof(DxvkScInfo);
    } else {
      binding.descriptorType = VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER;
      binding.descriptorCount = 1u;
    }

    VkDescriptorSetLayoutCreateInfo info = { VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO };
    info.bindingCount = 1u;
    info.pBindings = &binding;

    if (m_device->canUseDescriptorBuffer())
      info.flags |= VK_DESCRIPTOR_SET_LAYOUT_CREATE_DESCRIPTOR_BUFFER_BIT_EXT;

    VkDescriptorSetLayout layout = VK_NULL_HANDLE;
    VkResult vr = vk->vkCreateDescriptorSetLayout(vk->device(), &info, nullptr, &layout);

    if (vr != VK_SUCCESS)
      throw DxvkError("DXVK: Failed to create spec data fallback layout");

    return layout;
  }

}
