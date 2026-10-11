"""Source/packaging regression gates for the opt-in FF7R pooled-memory A/B WCP.

These tests verify explicit policy invariants, but do not replace Android
Turnip runtime validation; tests run in GitHub Actions before cross-build.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
MEM = ROOT / "src/dxvk/dxvk_memory.cpp"
PACK = ROOT / "package-release.sh"


def effective_chunk_max(base_mib: int, mapped: bool, host_bits: int, experiment: bool):
    # Mirrors determineMaxChunkSize independently; use below to check
    # expected outcomes on 32-bit, 64-bit and device/mapped pools.
    value = base_mib // (16 if host_bits == 32 else 4) if mapped else base_mib
    if experiment:
        value = min(value, 32 if mapped else 64)
    return max(value, 4)


class PoolExperimentTests(unittest.TestCase):
    def setUp(self):
        self.source = MEM.read_text(encoding="utf-8")
        self.package = PACK.read_text(encoding="utf-8")

    def test_only_separate_build_can_enable_policy(self):
        s = self.source
        self.assertIn("#ifdef DXVK_SD865_POOL_WCP", s)
        self.assertIn('env::getEnvVar("DXVK_SD865_POOL_EXPERIMENT") == "1"', s)
        self.assertRegex(s, r"(?s)static bool sd865PoolExperimentEnabled\(\).*?#else\s+return false;")
        self.assertIn('DXVK_SD865_POOL_WCP:-0', self.package)
        self.assertIn("-DDXVK_SD865_POOL_WCP=1", self.package)
        self.assertIn("elif [", self.package)
        self.assertIn("DXVK_SD865_DIAG_WCP:-0", self.package)

    def test_pool_caps_for_native_64_and_32bit(self):
        self.assertEqual(effective_chunk_max(256, False, 64, False), 256)
        self.assertEqual(effective_chunk_max(256, True, 64, False), 64)
        self.assertEqual(effective_chunk_max(256, False, 64, True), 64)
        self.assertEqual(effective_chunk_max(256, True, 64, True), 32)
        self.assertEqual(effective_chunk_max(256, True, 32, False), 16)
        self.assertEqual(effective_chunk_max(256, True, 32, True), 16)
        self.assertIn("size = std::min<VkDeviceSize>(size, mappable ? VkDeviceSize(32ull << 20) : VkDeviceSize(64ull << 20))", self.source)

    def test_hvv_special_path_cannot_bypass_test_cap(self):
        s = self.source
        before = s.index("maxChunkSize = DxvkPageAllocator::MaxChunkSize /")
        override = s.index("maxChunkSize = selectedPool.maxChunkSize", before)
        guard = s.rfind("if (sd865PoolExperimentEnabled())", before, override)
        self.assertGreater(guard, before)
        self.assertIn("size * minResourcesPerChunk > maxChunkSize", s[override:override + 1600])

    def test_reclaim_only_truly_empty_chunks(self):
        s = self.source
        beginning = s.index("bool DxvkMemoryAllocator::freeEmptyChunksInPool(")
        end = s.index("int32_t DxvkMemoryAllocator::findEmptyChunkInPool(", beginning)
        chunk = s[beginning:end]
        check = chunk.index("pool.pageAllocator.pagesUsed(i)")
        freeing = chunk.index("freeDeviceMemory(type, chunk.memory)")
        self.assertLess(check, freeing)
        self.assertIn("if (sd865PoolExperimentEnabled())\\n      maxUnusedMemory = 0u;", chunk)
        self.assertIn("sd865PoolReclaimedChunks().fetch_add(1u", chunk)
        self.assertIn("sd865PoolReclaimedBytes().fetch_add(chunk.memory.size", chunk)

    def test_bda_and_driver_oom_retry_untouched(self):
        s = self.source
        self.assertIn("memoryFlags.flags |= VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT", s)
        self.assertIn("firstResult = vk->vkAllocateMemory(", s)
        self.assertIn("retryResult = vk->vkAllocateMemory(", s)
        self.assertIn("freeEmptyChunksInHeap(*type.heap, VkDeviceSize(-1)", s)
        self.assertIn("if (retryResult != VK_SUCCESS)", s)
        self.assertIn("stage=driver_retry", s)
        self.assertIn("stage=pool_exhausted", s)

    def test_log_signatures_and_caps(self):
        s = self.source
        self.assertIn("DXVK-SD865-POOL state=init", s)
        self.assertIn('" enabled=", sd865PoolExperimentEnabled() ? 1 : 0', s)
        self.assertIn('" empty_chunks_reclaimed="', s)
        self.assertIn('" empty_bytes_reclaimed="', s)
        self.assertIn('emitted.fetch_add(1u, std::memory_order_relaxed) < 128u', s)
        self.assertIn("DXVK-SD865-ALLOC state=diagnostic_wcp_loaded", s)

    def test_early_pressure_threshold_remains_driver_owned(self):
        s = self.source
        self.assertIn("heap.memoryBudget = memInfo.memoryHeaps[i].size;", s)
        self.assertIn("m_memHeaps[i].memoryBudget = std::min(", s)
        self.assertNotIn("memoryFlags.flags &= ~VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT", s)


if __name__ == "__main__":
    unittest.main()
