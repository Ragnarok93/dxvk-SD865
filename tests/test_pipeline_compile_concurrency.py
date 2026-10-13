"""Compile the actual optimized-pipeline lookup against a deterministic fake compiler.

The fake only replaces Vulkan compilation; the production map lookup/publication
body and completion object are extracted unchanged from the source.
"""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def extract(source, start, end):
    return source[source.index(start):source.index(end, source.index(start))]


class PipelineCompileConcurrencyTests(unittest.TestCase):
    def test_variant_overlap_deduplication_failure_and_rehash(self):
        cpp = (ROOT / "src/dxvk/dxvk_graphics.cpp").read_text()
        header = (ROOT / "src/dxvk/dxvk_graphics.h").read_text()
        lookup = extract(cpp, "  VkPipeline DxvkGraphicsPipeline::getOptimizedPipeline(",
                         "  " + ("std::pair<VkResult, VkPipeline>" if
                         "std::pair<VkResult, VkPipeline> DxvkGraphicsPipeline::createOptimizedPipeline" in cpp
                         else "VkPipeline") + " DxvkGraphicsPipeline::createOptimizedPipeline(")
        has_completion = "struct DxvkGraphicsPipelineFastInstanceObject" in header
        completion = extract(header, "  struct DxvkGraphicsPipelineFastInstanceObject {",
                             "  /**") if has_completion else ""
        value_type = "DxvkGraphicsPipelineFastInstanceObject" if has_completion else "VkPipeline"
        return_type = "std::pair<VkResult, VkPipeline>" if has_completion else "VkPipeline"
        result = "return {key.id == 9 ? VK_ERROR_UNKNOWN : VK_SUCCESS, key.id == 9 ? 0u : key.id + 100u};" if has_completion else "return key.id == 9 ? 0u : key.id + 100u;"
        harness = r'''
#include <atomic>
#include <cassert>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <future>
#include <mutex>
#include <stdexcept>
#include <thread>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>
using VkPipeline = uintptr_t;
using VkResult = int;
constexpr VkPipeline VK_NULL_HANDLE = 0;
constexpr VkResult VK_SUCCESS = 0, VK_NOT_READY = 1, VK_ERROR_UNKNOWN = -13;
namespace dxvk {
namespace sync { template<typename Fn> void spin(unsigned, Fn fn) { while (!fn()) std::this_thread::yield(); } }
struct DxvkGraphicsPipelineStateInfo { unsigned id; };
struct DxvkGraphicsPipelineFastInstanceKey {
  unsigned id;
  DxvkGraphicsPipelineFastInstanceKey(void*, int, const DxvkGraphicsPipelineStateInfo& s, int, int) : id(s.id) { }
};
struct Hash { size_t operator()(const DxvkGraphicsPipelineFastInstanceKey& k) const { return k.id; } };
struct Eq { bool operator()(const DxvkGraphicsPipelineFastInstanceKey& a, const DxvkGraphicsPipelineFastInstanceKey& b) const { return a.id == b.id; } };
COMPLETION
class DxvkGraphicsPipeline {
public:
  void* m_device = nullptr;
  int m_shaders = 0, m_flags = 0, m_specConstantMask = 0;
  std::mutex m_fastMutex;
  std::unordered_map<DxvkGraphicsPipelineFastInstanceKey, VALUE, Hash, Eq> m_fastPipelines;
  std::atomic<unsigned> compileCount = 0, entered = 0;
  std::atomic<bool> release = false;
  bool block = true, throwing = false;
  VkPipeline getOptimizedPipeline(const DxvkGraphicsPipelineStateInfo&);
  RETURN createOptimizedPipeline(const DxvkGraphicsPipelineFastInstanceKey& key) {
    ++compileCount;
    ++entered;
    if (block) while (!release.load()) std::this_thread::yield();
    if (throwing) throw std::runtime_error("compile exception");
    RESULT
  }
};
LOOKUP
}
using namespace dxvk;
using namespace std::chrono_literals;
void waitFor(const std::atomic<unsigned>& count, unsigned n) {
  auto until = std::chrono::steady_clock::now() + 2s;
  while (count.load() < n && std::chrono::steady_clock::now() < until) std::this_thread::yield();
  assert(count.load() >= n);
}
int main() {
  { // Distinct variants must reach the compiler concurrently.
    DxvkGraphicsPipeline p;
    auto a = std::async(std::launch::async, [&] { return p.getOptimizedPipeline({1}); });
    waitFor(p.entered, 1);
    auto b = std::async(std::launch::async, [&] { return p.getOptimizedPipeline({2}); });
    waitFor(p.entered, 2);
    p.release = true;
    assert(a.get() == 101 && b.get() == 102);
  }
  { // Identical keys share the same result and compile only once.
    DxvkGraphicsPipeline p;
    std::vector<std::future<VkPipeline>> calls;
    for (unsigned i = 0; i < 16; ++i) calls.push_back(std::async(std::launch::async, [&] { return p.getOptimizedPipeline({3}); }));
    waitFor(p.entered, 1);
    p.release = true;
    for (auto& call : calls) assert(call.get() == 103);
    assert(p.compileCount == 1);
  }
  { // A failed compile is terminal, rather than an indefinite wait/retry.
    DxvkGraphicsPipeline p;
    p.block = false;
    assert(p.getOptimizedPipeline({9}) == 0);
    assert(p.getOptimizedPipeline({9}) == 0);
    assert(p.compileCount == 1);
  }
  { // Rehash the same map while its first compilation remains pending.
    DxvkGraphicsPipeline p;
    auto first = std::async(std::launch::async, [&] { return p.getOptimizedPipeline({4}); });
    waitFor(p.entered, 1);
    { std::lock_guard lock(p.m_fastMutex); p.m_fastPipelines.rehash(4096); }
    p.release = true;
    assert(first.get() == 104);
    assert(p.getOptimizedPipeline({4}) == 104);
  }
  { // An exceptional compiler path must publish a terminal failure too.
    DxvkGraphicsPipeline p;
    p.throwing = true;
    auto first = std::async(std::launch::async, [&] {
      try { p.getOptimizedPipeline({5}); } catch (const std::runtime_error&) { return true; }
      return false;
    });
    waitFor(p.entered, 1);
    auto duplicate = std::async(std::launch::async, [&] { return p.getOptimizedPipeline({5}); });
    p.release = true;
    assert(first.get());
    assert(duplicate.wait_for(2s) == std::future_status::ready);
    assert(duplicate.get() == 0);
    assert(p.compileCount == 1);
  }
}
'''
        for name, value in {"COMPLETION": completion, "VALUE": value_type,
                            "RETURN": return_type, "RESULT": result,
                            "LOOKUP": lookup}.items():
            harness = harness.replace(name, value)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "concurrency.cpp"
            binary = Path(directory) / "concurrency"
            source.write_text(harness)
            subprocess.run(["g++", "-std=c++17", "-O2", "-pthread", "-D_GLIBCXX_DEBUG",
                            str(source), "-o", str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, capture_output=True, timeout=12)


if __name__ == "__main__":
    unittest.main()
