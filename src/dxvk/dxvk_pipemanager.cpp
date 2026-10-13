#include <optional>
#include <chrono>

#include "dxvk_device.h"
#include "dxvk_pipemanager.h"
#include "../util/util_ff7r_timing.h"

namespace dxvk {
  
  DxvkPipelineWorkers::DxvkPipelineWorkers(
          DxvkDevice*                     device)
  : m_device(device) {

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
      // Use all available cores by default
      uint32_t workerCount = dxvk::thread::hardware_concurrency();

      if (workerCount <  1) workerCount =  1;
      if (workerCount > 64) workerCount = 64;

      // Reduce worker count on 32-bit to save adderss space
      if (env::is32BitHostPlatform())
        workerCount = std::min(workerCount, 16u);

      if (m_device->config().numCompilerThreads > 0)
        workerCount = m_device->config().numCompilerThreads;

      // Number of workers that can process pipeline pipelines with normal
      // priority. Any other workers can only build high-priority pipelines.
      uint32_t npWorkerCount = std::max(((workerCount - 1) * 5) / 7, 1u);
      uint32_t lpWorkerCount = std::max(((workerCount - 1) * 2) / 7, 1u);

      m_workers.reserve(workerCount);

      for (size_t i = 0; i < workerCount; i++) {
        DxvkPipelinePriority priority = DxvkPipelinePriority::Normal;

        if (m_device->canUseGraphicsPipelineLibrary()) {
          if (i >= npWorkerCount)
            priority = DxvkPipelinePriority::High;
          else if (i < lpWorkerCount)
            priority = DxvkPipelinePriority::Low;
        }

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

    // Disabled by default; no clock reads or extra atomics on the hot
    // compilation path unless a targeted FF7R diagnostic run opts in.
    static const bool ff7rPerfEnabled = env::getEnvVar("DXVK_FF7R_METRICS") == "1";
    static std::atomic<uint64_t> libraryCount { 0 }, libraryUs { 0 };
    static std::atomic<uint64_t> optimizedCount { 0 }, optimizedUs { 0 };
    static std::atomic<uint64_t> over10ms { 0 }, over33ms { 0 }, totalSamples { 0 };

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

      auto started = ff7rPerfEnabled
        ? std::chrono::steady_clock::now()
        : std::chrono::steady_clock::time_point { };

      if (entry.pipelineLibrary) {
        entry.pipelineLibrary->compilePipeline();
      } else if (entry.graphicsPipeline) {
        entry.graphicsPipeline->compilePipeline(entry.graphicsState);
        entry.graphicsPipeline->releasePipeline();
      }

      if (ff7rPerfEnabled && (entry.pipelineLibrary || entry.graphicsPipeline)) {
        uint64_t elapsedUs = uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(
          std::chrono::steady_clock::now() - started).count());
        if (entry.pipelineLibrary) {
          libraryUs.fetch_add(elapsedUs, std::memory_order_relaxed);
          libraryCount.fetch_add(1, std::memory_order_relaxed);
        } else {
          optimizedUs.fetch_add(elapsedUs, std::memory_order_relaxed);
          optimizedCount.fetch_add(1, std::memory_order_relaxed);
        }
        if (elapsedUs >= 10000)
          over10ms.fetch_add(1, std::memory_order_relaxed);
        if (elapsedUs >= 33000)
          over33ms.fetch_add(1, std::memory_order_relaxed);
        uint64_t samples = totalSamples.fetch_add(1, std::memory_order_relaxed) + 1;
        if (samples == 1 || samples % 64 == 0) {
          uint64_t libs = libraryCount.load(std::memory_order_relaxed);
          uint64_t opts = optimizedCount.load(std::memory_order_relaxed);
          Logger::info(str::format(
            "DXVK-FF7R-PIPELINES: ts_us=", Ff7rTimingCounter::timeUs(Ff7rTimingCounter::Clock::now()),
            " samples=", samples,
            " pending=", m_tasksTotal.load(std::memory_order_relaxed) - m_tasksCompleted.load(std::memory_order_relaxed),
            " libraries=", libs,
            " library_mean_us=", libs ? libraryUs.load(std::memory_order_relaxed) / libs : 0,
            " optimized=", opts,
            " optimized_mean_us=", opts ? optimizedUs.load(std::memory_order_relaxed) / opts : 0,
            " over_10ms=", over10ms.load(std::memory_order_relaxed),
            " over_33ms=", over33ms.load(std::memory_order_relaxed)));
        }
      }

      m_tasksCompleted += 1;
    }
  }


  DxvkPipelineManager::DxvkPipelineManager(
          DxvkDevice*         device)
  : m_device    (device),
    m_workers   (device) {
    Logger::info(str::format("DXVK: Graphics pipeline libraries ",
      (m_device->canUseGraphicsPipelineLibrary() ? "supported" : "not supported")));

    if (m_device->canUseGraphicsPipelineLibrary()) {
      auto library = createNullFsPipelineLibrary();
      library->compilePipeline();
    }
  }
  
  
  DxvkPipelineManager::~DxvkPipelineManager() {
    
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

    DxvkShaderPipelineLibrary* vsLibrary = nullptr;
    DxvkShaderPipelineLibrary* fsLibrary = nullptr;

    if (m_device->canUseGraphicsPipelineLibrary()) {
      DxvkShaderPipelineLibraryKey vsKey;
      vsKey.addShader(shaders.vs);

      if (shaders.tcs != nullptr) vsKey.addShader(shaders.tcs);
      if (shaders.tes != nullptr) vsKey.addShader(shaders.tes);
      if (shaders.gs  != nullptr) vsKey.addShader(shaders.gs);

      if (vsKey.canUsePipelineLibrary()) {
        vsLibrary = findPipelineLibraryLocked(vsKey);

        if (!vsLibrary) {
          // If multiple shader stages are participating, create a
          // pipeline library so that it can potentially be reused.
          // Don't dispatch the pipeline library to a worker thread
          // since it should be compiled on demand anyway.
          vsLibrary = createPipelineLibraryLocked(vsKey);
        }
      }

      if (vsLibrary) {
        DxvkShaderPipelineLibraryKey fsKey;

        if (shaders.fs != nullptr)
          fsKey.addShader(shaders.fs);

        fsLibrary = findPipelineLibraryLocked(fsKey);
      }
    }

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
    if (canPrecompileShader(shader)) {
      DxvkShaderPipelineLibraryKey key;
      key.addShader(shader);

      auto library = createShaderPipelineLibrary(key);
      m_workers.compilePipelineLibrary(library, DxvkPipelinePriority::Normal);
    }
  }


  void DxvkPipelineManager::requestCompileShader(
    const Rc<DxvkShader>&         shader) {
    if (!shader->needsLibraryCompile())
      return;

    // Dispatch high-priority compile job
    DxvkShaderPipelineLibraryKey key;
    key.addShader(shader);

    auto library = findPipelineLibrary(key);

    if (library)
      m_workers.compilePipelineLibrary(library, DxvkPipelinePriority::High);

    // Notify immediately so that this only gets called
    // once, even if compilation does ot start immediately
    shader->notifyLibraryCompile();
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


  DxvkShaderPipelineLibrary* DxvkPipelineManager::createNullFsPipelineLibrary() {
    std::lock_guard<dxvk::mutex> lock(m_pipelineMutex);
    DxvkShaderPipelineLibraryKey key;

    auto iter = m_shaderLibraries.emplace(
      std::piecewise_construct,
      std::tuple(),
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
    if (pair == m_shaderLibraries.end())
      return nullptr;

    return &pair->second;
  }


  bool DxvkPipelineManager::canPrecompileShader(
    const Rc<DxvkShader>& shader) const {
    if (!shader->canUsePipelineLibrary(true))
      return false;

    if (shader->info().stage == VK_SHADER_STAGE_COMPUTE_BIT)
      return true;

    return m_device->canUseGraphicsPipelineLibrary();
  }

}
