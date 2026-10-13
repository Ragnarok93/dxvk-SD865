#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstddef>

namespace dxvk {

  // Opt-in CPU DXGI Present completion-cadence sampler. These are not GPU
  // execution timestamps, nor display scanout / LSFG-generated frame times.
  // No allocation or sorting occurs on individual present calls.
  class Ff7rPresentMetrics {
  public:
    static constexpr size_t WindowSize = 256;
    using Clock = std::chrono::steady_clock;

    struct Window {
      uint32_t sampleCount;
      uint32_t p50Us;
      uint32_t p95Us;
      uint32_t p99Us;
      uint32_t maxUs;
      uint32_t meanUs;
    };

    bool add(Clock::time_point now, Window& out) {
      if (!m_hasPrevious) {
        m_previous = now;
        m_hasPrevious = true;
        return false;
      }

      auto elapsed = std::chrono::duration_cast<std::chrono::microseconds>(now - m_previous).count();
      m_previous = now;

      // Ignore implausible/wrapped deltas and clear intervals across pauses,
      // load screens or suspend/resume. Keep the window scene-local.
      if (elapsed <= 0 || elapsed > 3000000) {
        m_count = 0;
        return false;
      }

      m_values[m_count++] = uint32_t(elapsed);
      if (m_count != WindowSize)
        return false;

      uint64_t sum = 0;
      for (uint32_t value : m_values)
        sum += value;

      std::sort(m_values.begin(), m_values.end());
      out.sampleCount = WindowSize;
      out.p50Us = percentile(50);
      out.p95Us = percentile(95);
      out.p99Us = percentile(99);
      out.maxUs = m_values.back();
      out.meanUs = uint32_t(sum / WindowSize);
      m_count = 0;
      return true;
    }

  private:
    uint32_t percentile(uint32_t p) const {
      const size_t index = (WindowSize * p + 99) / 100 - 1;
      return m_values[index];
    }

    std::array<uint32_t, WindowSize> m_values = { };
    Clock::time_point m_previous = { };
    uint32_t m_count = 0;
    bool m_hasPrevious = false;
  };

}
