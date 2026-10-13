import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / 'tools' / 'ff7r_perf_compare.py'
spec = importlib.util.spec_from_file_location('ff7r_perf_compare', SCRIPT)
perf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(perf)


class PerfCompareTest(unittest.TestCase):
    def test_older_logs_cannot_claim_speedup(self):
        with tempfile.TemporaryDirectory() as temp:
            a = Path(temp) / 'a.log'
            b = Path(temp) / 'b.log'
            a.write_text('DXVK: Using 8 compiler threads\n')
            b.write_text('DXVK: Graphics pipeline libraries supported\n')
            result = perf.compare(a, b)
            self.assertFalse(result['benchmark_valid'])
            self.assertEqual(result['candidate']['present_windows'], 0)
            self.assertNotIn('p95_window_median_delta_percent', result)

    def test_zip_windows_and_task_snapshots(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'capture.zip'
            with zipfile.ZipFile(p, 'w') as z:
                lines = [f'DXVK-FF7R-FRAMES: present_id={256*(i+1)} count=256 mean_us=33333 p50_us=33333 p95_us={34000+i*1000} p99_us=44000 max_us=60000' for i in range(3)]
                lines.append('DXVK-FF7R-PIPELINES: samples=64 libraries=60 library_mean_us=300 optimized=4 optimized_mean_us=500 over_10ms=0 over_33ms=0')
                lines.append('DXVK-FF7R-ONDEMAND: samples=64 mean_us=200 over_10ms=1 over_33ms=0')
                lines.append('DXVK-FF7R-GPU-WAIT: ts_us=789000 samples=64 mean_us=3500 max_us=41000 over_10ms=2 over_33ms=1')
                lines.append('DXVK-FF7R-QUEUE-SUBMIT: ts_us=788000 samples=64 mean_us=200 max_us=500 over_10ms=0 over_33ms=0')
                z.writestr('foo/ff7remake__dxgi.log', '\n'.join(lines))
            result = perf.compare(p, p)
            self.assertTrue(result['benchmark_valid'])
            self.assertEqual(result['candidate']['sampled_intervals'], 768)
            self.assertEqual(result['candidate']['median_window_p95_ms'], 35)
            self.assertEqual(result['candidate']['pipeline_latest_snapshot']['samples'], 64)
            self.assertEqual(result['candidate']['on_demand_latest_snapshot']['over_10ms'], 1)
            self.assertEqual(result['candidate']['queue_latest_snapshots']['GPU-WAIT']['max_us'], 41000)
            self.assertEqual(result['candidate']['queue_latest_snapshots']['QUEUE-SUBMIT']['samples'], 64)
            self.assertIsNone(result['candidate']['queue_latest_snapshots']['CS-WAIT'])
            self.assertEqual(result['candidate']['last_8_window_p95_ms'], 35)
            self.assertEqual(result['p95_window_median_delta_percent'], 0)


if __name__ == '__main__':
    unittest.main()
