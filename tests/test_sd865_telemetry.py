"""DXVK-SD865 performance-log parser regression cases."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from sd865_telemetry import pairs, summarize


class TelemetryTests(unittest.TestCase):
    def test_pairs(self):
        self.assertEqual(pairs("shaderTasks=12/34 barriers=7 peakPending=9"),
                         {"shaderTasks": {"completed": 12, "total": 34},
                          "barriers": 7, "peakPending": 9})

    def test_windows_are_normalized(self):
        lines = [
            "wine: DXVK-SD865 counters over 300 present requests: renderPasses=900 barriers=1200 draws=3000 dispatches=60 submits=500 gpuSyncs=5 gpuWaitUs=8000 csWaitUs=1000 shaderTasks=12/15",
            "DXVK-SD865 compiler sample: tasks=128 total=150 avgQueueWaitUs=70 avgCompileUs=400 maxQueueWaitUs=6000 maxCompileUs=22000 peakPending=17",
            "DXVK-SD865 counters over 300 present requests: renderPasses=600 barriers=900 draws=2400 dispatches=40 submits=400 gpuSyncs=2 gpuWaitUs=4000 csWaitUs=2000 shaderTasks=150/180",
            "DXVK-SD865 compiler totals: completed=180 scheduled=190 queuedWaitUs=12000 compileWorkUs=80000 peakQueueWaitUs=6000 peakCompileUs=22000 peakPending=17",
        ]
        report = summarize(lines)
        self.assertEqual(report["presentRequests"], 600)
        self.assertEqual(report["windowCount"], 2)
        self.assertEqual(report["totals"]["renderPasses"], 1500)
        self.assertEqual(report["perPresent"]["renderPasses"], 2.5)
        self.assertEqual(report["totals"]["barriers"], 2100)
        self.assertEqual(report["latestShaderTasks"], {"completed": 150, "total": 180})
        self.assertEqual(report["latestCompilerSample"]["peakPending"], 17)
        self.assertEqual(report["finalCompilerTotals"]["completed"], 180)

    def test_compile_only_is_valid(self):
        report = summarize(["DXVK-SD865 compiler sample: tasks=128 total=130 avgCompileUs=50"])
        self.assertEqual(report["presentRequests"], 0)
        self.assertEqual(report["latestCompilerSample"]["tasks"], 128)

    def test_disabled_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "No DXVK-SD865 profiling records"):
            summarize(["normal DXVK startup log", "DXVK: Using 4 compiler threads"])


if __name__ == "__main__":
    unittest.main()
