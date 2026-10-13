"""Regression tests for opt-in DXVK-SD865 memory-allocation diagnostics."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ff7r_alloc_trace_report import summarize

SOURCE = Path(__file__).resolve().parents[1] / "src/dxvk/dxvk_memory.cpp"

DRIVER = (
    "err: DXVK-SD865-ALLOC stage=driver_retry "
    "first_vkresult=-2 first_name=VK_ERROR_OUT_OF_DEVICE_MEMORY "
    "retry_vkresult=0 retry_name=VK_SUCCESS recovered=1 "
    "first_attempt_id=403 retry_attempt_id=404 "
    "requested_bytes=22369792 memory_type=1 heap=0 heap_size_bytes=4294967296 dedicated=0 "
    "dxvk_allocated_bytes=4110417920 dxvk_used_bytes=3913285632 "
    "dxvk_budget_bytes=5012193280 driver_allocated_bytes=3958376448 "
    "driver_budget_bytes=5006950400 pool_experiment=1 "
    "empty_chunks_reclaimed=18 empty_bytes_reclaimed=67108864"
)


class AllocTraceTests(unittest.TestCase):
    def test_recover_and_code_reported(self):
        report = summarize([DRIVER])
        self.assertEqual(report["event_count"], 1)
        self.assertEqual(report["events"][0]["first_vkresult"], -2)
        self.assertEqual(report["events"][0]["first_attempt_id"], 403)
        self.assertEqual(report["events"][0]["retry_attempt_id"], 404)
        self.assertEqual(report["events"][0]["heap_size_bytes"], 4294967296)
        self.assertEqual(report["events"][0]["pool_experiment"], 1)
        self.assertEqual(report["events"][0]["empty_chunks_reclaimed"], 18)
        self.assertEqual(report["events"][0]["empty_bytes_reclaimed"], 67108864)
        self.assertEqual(report["events"][0]["first_name"], "VK_ERROR_OUT_OF_DEVICE_MEMORY")
        self.assertEqual(report["events"][0]["retry_vkresult"], 0)
        self.assertEqual(report["outcomes"]["recovered_after_retry"], 1)

    def test_unrecovered_driver_allocation(self):
        report = summarize([DRIVER.replace("retry_vkresult=0", "retry_vkresult=-1")
                            .replace("retry_name=VK_SUCCESS", "retry_name=VK_ERROR_OUT_OF_HOST_MEMORY")
                            .replace("recovered=1", "recovered=0")])
        self.assertEqual(report["outcomes"]["failed_after_retry"], 1)
        self.assertEqual(report["events"][0]["retry_name"], "VK_ERROR_OUT_OF_HOST_MEMORY")

    def test_pool_exhausted_is_not_implicitly_driver_failure(self):
        report = summarize(["DXVK-SD865-ALLOC stage=pool_exhausted "
                            "requested_bytes=100 alignment=256 "
                            "eligible_memory_types_mask=0 no_allocation_mode=1"])
        self.assertEqual(report["by_stage"], {"pool_exhausted": 1})
        self.assertNotIn("first_vkresult", report["events"][0])

    def test_budget_guard_separate(self):
        report = summarize(["DXVK-SD865-ALLOC stage=budget_guard driver_call=0 "
                            "requested_bytes=4096 memory_type=1 dxvk_budget_bytes=123"])
        self.assertEqual(report["events"][0]["driver_call"], 0)
        self.assertEqual(report["by_stage"], {"budget_guard": 1})

    def test_wine_prefix_and_missing_marker(self):
        self.assertEqual(summarize(["Wine warning 101"])["status"], "no_diagnostic_marker")
        self.assertEqual(summarize(["0150:err: trace junk", DRIVER])["event_count"], 1)

    def test_bad_numbers_and_untrusted_code_are_ignored(self):
        report = summarize([DRIVER.replace("memory_type=1", "memory_type=XYZ")
                            .replace("first_name=VK_ERROR_OUT_OF_DEVICE_MEMORY",
                                     "first_name=USER_PSEUDO_RESULT")])
        self.assertNotIn("memory_type", report["events"][0])
        self.assertNotIn("first_name", report["events"][0])

    def test_cpp_feature_gate_and_retry_preserved(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertNotIn('env::getEnvVar("DXVK_SD865_ALLOC_TRACE") == "1"', source)
        self.assertIn('env::getEnvVar("DXVK_SD865_ALLOC_TRACE") != "0"', source)
        self.assertIn('#ifdef DXVK_SD865_ALLOC_DIAG_WCP', source)
        self.assertIn('DXVK-SD865-ALLOC state=ready', source)
        script = (SOURCE.parents[2] / "package-release.sh").read_text(encoding="utf-8")
        self.assertIn("DXVK_SD865_DIAG_WCP", script)
        self.assertIn("-Dcpp_args=-DDXVK_SD865_ALLOC_DIAG_WCP=1", script)
        self.assertIn('sd865AllocTraceNextAttempt()', source)
        self.assertIn('" heap_size_bytes="', source)
        self.assertIn('" first_attempt_id="', source)
        self.assertIn('" retry_attempt_id="', source)
        self.assertIn("firstResult = vk->vkAllocateMemory(", source)
        self.assertIn("retryResult = vk->vkAllocateMemory(", source)
        self.assertIn("if (retryResult != VK_SUCCESS)", source)
        self.assertIn("freeEmptyChunksInHeap(*type.heap, VkDeviceSize(-1)", source)
        self.assertIn("sd865AllocTraceAllowEvent()", source)
        self.assertIn("emitted.fetch_add(1u, std::memory_order_relaxed) < 128u", source)
        for stage in ("driver_retry", "budget_guard", "pool_exhausted", "dedicated_exhausted"):
            self.assertIn("DXVK-SD865-ALLOC stage=" + stage, source)
        self.assertNotIn("VK_SUCCESS; // spoof", source)


if __name__ == "__main__":
    unittest.main()
