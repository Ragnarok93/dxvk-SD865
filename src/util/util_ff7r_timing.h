#pragma once

#include <atomic>
#include <chrono>
#include <cstdint>

namespace dxvk {

  // Thread-safe opt-in CPU timing aggregate. This is wall-clock time spent
  // in a CPU API call, NOT a Vulkan GPU timestamp or a scanout measurement.
  // Each call site owns its own counters. No heap allocations.
  class Ff7rTimingCounter {
  public:
    using Clock = std::chrono::steady_clock;

    struct Snapshot {
      uint64_t count;
      uint64_t meanUs;
      uint64_t maxUs;
      uint64_t over10ms;
      uint64_t over33ms;
    };

    bool record(uint64_t elapsedUs) noexcept {
      m_totalUs.fetch_add(elapsedUs, std::memory_order_relaxed);
      if (elapsedUs >= 10000)
        m_over10ms.fetch_add(1, std::memory_order_relaxed);
      if (elapsedUs >= 33000)
        m_over33ms.fetch_add(1, std::memory_order_relaxed);

      uint64_t oldMax = m_maxUs.load(std::memory_order_relaxed);
      while (oldMax < elapsedUs && !m_maxUs.compare_exchange_weak(
        oldMax, elapsedUs, std::memory_order_relaxed)) { }

      // Publish the count last; snapshots are approximate across workers.
      uint64_t count = m_count.fetch_add(1, std::memory_order_release) + 1;
      return count == 1 || (count % 64 == 0);
    }

    Snapshot snapshot() const noexcept {
      uint64_t count = m_count.load(std::memory_order_acquire);
      return {
        count,
        count ? m_totalUs.load(std::memory_order_relaxed) / count : 0,
        m_maxUs.load(std::memory_order_relaxed),
        m_over10ms.load(std::memory_order_relaxed),
        m_over33ms.load(std::memory_order_relaxed),
      };
    }

    static uint64_t timeUs(Clock::time_point t) noexcept {
      return uint64_t(std::chrono::duration_cast<std::chrono::microseconds>(
        t.time_since_epoch()).count());
    }

  private:
    std::atomic<uint64_t> m_count { 0 };
    std::atomic<uint64_t> m_totalUs { 0 };
    std::atomic<uint64_t> m_maxUs { 0 };
    std::atomic<uint64_t> m_over10ms { 0 };
    std::atomic<uint64_t> m_over33ms { 0 };
  };

}
