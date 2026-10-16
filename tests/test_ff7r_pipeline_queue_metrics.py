"""Source-contract checks for opt-in per-pipeline-type queue-wait telemetry."""
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "src/dxvk/dxvk_pipemanager.cpp"


class PipelineQueueMetricsTest(unittest.TestCase):
    def test_waits_are_split_by_compilation_task_type(self):
        source = SOURCE.read_text(encoding="utf-8")
        for token in (
            "libraryQueueWaitUs", "libraryQueueWaitCount",
            "libraryQueueWaitOver10ms", "libraryQueueWaitOver33ms",
            "optimizedQueueWaitUs", "optimizedQueueWaitCount",
            "optimizedQueueWaitOver10ms", "optimizedQueueWaitOver33ms",
            '" library_queue_wait_mean_us="',
            '" optimized_queue_wait_mean_us="',
        ):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_metrics_remain_opt_in(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn('env::getEnvVar("DXVK_FF7R_METRICS") == "1"', source)
        self.assertIn("if (ff7rPerfEnabled && entry.enqueuedAt", source)


if __name__ == "__main__":
    unittest.main()
