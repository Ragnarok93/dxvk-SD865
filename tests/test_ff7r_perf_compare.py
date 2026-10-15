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
            a.write_text('DXVK: Using 8 compiler threads\nDXVK-FF7R-PIPELINES: samples=64 libraries=60 optimized=4\n')
            b.write_text('DXVK: Graphics pipeline libraries supported\nDXVK-FF7R-PIPELINES: samples=64 libraries=55 optimized=9\n')
            result = perf.compare(a, b)
            self.assertFalse(result['benchmark_valid'])
            self.assertNotIn('pipeline_library_mean_us_delta', result)
            self.assertNotIn('pipeline_queue_wait_mean_us_delta', result)
            self.assertEqual(result['candidate']['present_windows'], 0)
            self.assertNotIn('p95_window_median_delta_percent', result)

    def test_zip_windows_and_task_snapshots(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp) / 'capture.zip'
            with zipfile.ZipFile(p, 'w') as z:
                lines = [f'DXVK-FF7R-FRAMES: present_id={256*(i+1)} count=256 mean_us=33333 p50_us=33333 p95_us={34000+i*1000} p99_us=44000 max_us=60000' for i in range(3)]
                lines.append('DXVK-FF7R-PIPELINES: samples=64 libraries=60 library_mean_us=300 optimized=4 optimized_mean_us=500 over_10ms=0 over_33ms=0 queue_wait_samples=64 queue_wait_mean_us=12000 queue_wait_over_10ms=8 queue_wait_over_33ms=2')
                lines.append('DXVK-FF7R-ONDEMAND: samples=64 mean_us=200 over_10ms=1 over_33ms=0')
                lines.append('DXVK-FF7R-GPU-WAIT: ts_us=789000 samples=64 mean_us=3500 max_us=41000 over_10ms=2 over_33ms=1')
                lines.append('DXVK-FF7R-QUEUE-SUBMIT: ts_us=788000 samples=64 mean_us=200 max_us=500 over_10ms=0 over_33ms=0')
                z.writestr('foo/ff7remake__dxgi.log', '\n'.join(lines))
            result = perf.compare(p, p)
            self.assertTrue(result['benchmark_valid'])
            self.assertEqual(result['candidate']['sampled_intervals'], 768)
            self.assertEqual(result['candidate']['median_window_p95_ms'], 35)
            self.assertEqual(result['candidate']['pipeline_latest_snapshot']['samples'], 64)
            self.assertEqual(result['candidate']['pipeline_latest_snapshot']['queue_wait_mean_us'], 12000)
            self.assertEqual(result['candidate']['pipeline_latest_snapshot']['queue_wait_over_10ms'], 8)
            self.assertEqual(result['candidate']['pipeline_latest_snapshot']['queue_wait_over_33ms'], 2)
            self.assertEqual(result['candidate']['on_demand_latest_snapshot']['over_10ms'], 1)
            self.assertEqual(result['candidate']['queue_latest_snapshots']['GPU-WAIT']['max_us'], 41000)
            self.assertEqual(result['candidate']['queue_latest_snapshots']['QUEUE-SUBMIT']['samples'], 64)
            self.assertIsNone(result['candidate']['queue_latest_snapshots']['CS-WAIT'])
            self.assertEqual(result['candidate']['last_8_window_p95_ms'], 35)
            self.assertEqual(result['p95_window_median_delta_percent'], 0)


    def test_lookup_cache_metrics_and_duplicate_present_ids(self):
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / 'lookup.log'
            log.write_text('\n'.join([
                'DXVK-FF7R-FRAMES: present_id=1 count=256 mean_us=12000 p50_us=10000 p95_us=20000 p99_us=30000 max_us=40000',
                'DXVK-FF7R-FRAMES: present_id=1 count=256 mean_us=12000 p50_us=10000 p95_us=21000 p99_us=30000 max_us=40000',
                'DXVK-FF7R-FRAMES: present_id=2 count=256 mean_us=12000 p50_us=10000 p95_us=24000 p99_us=30000 max_us=40000',
                'DXVK-FF7R-LOOKUP: samples=16 mean_ns=800 mean_entries=2 cache_hit_pct=75 max_ns=5000 max_entries=40',
            ]), encoding='utf-8')
            result = perf.parse(log)

        self.assertEqual(result['present_windows'], 2)
        self.assertEqual(result['sampled_intervals'], 512)
        self.assertEqual(result['median_window_p95_ms'], 22.5)
        self.assertEqual(result['pipeline_lookup_latest_snapshot']['mean_ns'], 800)
        self.assertEqual(result['pipeline_lookup_latest_snapshot']['cache_hit_pct'], 75)

    def test_comparison_reports_frame_and_lookup_deltas_from_zip(self):
        with tempfile.TemporaryDirectory() as temp:
            baseline = Path(temp) / 'baseline.log'
            candidate = Path(temp) / 'candidate.zip'
            baseline.write_text('\n'.join([
                'DXVK-FF7R-FRAMES: present_id=1 count=256 mean_us=12000 p50_us=10000 p95_us=20000 p99_us=30000 max_us=40000',
                'DXVK-FF7R-FRAMES: present_id=2 count=256 mean_us=12000 p50_us=10000 p95_us=22000 p99_us=30000 max_us=40000',
                'DXVK-FF7R-FRAMES: present_id=3 count=256 mean_us=12000 p50_us=10000 p95_us=24000 p99_us=30000 max_us=40000',
                'DXVK-FF7R-LOOKUP: samples=16 mean_ns=1000 mean_entries=8 cache_hit_pct=10 max_ns=5000 max_entries=40',
            ]), encoding='utf-8')
            candidate_log = '\n'.join([
                'DXVK-FF7R-FRAMES: present_id=1 count=256 mean_us=12000 p50_us=10000 p95_us=18000 p99_us=30000 max_us=40000',
                'DXVK-FF7R-FRAMES: present_id=2 count=256 mean_us=12000 p50_us=10000 p95_us=20000 p99_us=30000 max_us=40000',
                'DXVK-FF7R-FRAMES: present_id=3 count=256 mean_us=12000 p50_us=10000 p95_us=22000 p99_us=30000 max_us=40000',
                'DXVK-FF7R-LOOKUP: samples=16 mean_ns=700 mean_entries=1 cache_hit_pct=80 max_ns=5000 max_entries=40',
            ])
            with zipfile.ZipFile(candidate, 'w') as archive:
                archive.writestr('logs/game.log', candidate_log)
            result = perf.compare(baseline, candidate)

        self.assertTrue(result['benchmark_valid'])
        self.assertEqual(result['p95_window_median_delta_ms'], -2.0)
        self.assertEqual(result['pipeline_lookup_mean_ns_delta'], -300)
        self.assertEqual(result['pipeline_lookup_mean_entries_delta'], -7)
        self.assertEqual(result['pipeline_lookup_cache_hit_pct_delta'], 70)


    def test_pipeline_queue_wait_comparison_deltas(self):
        with tempfile.TemporaryDirectory() as temp:
            baseline = Path(temp) / 'baseline.log'
            candidate = Path(temp) / 'candidate.log'

            def capture(path, queue_mean, over10, over33, library_mean, optimized_mean):
                lines = [
                    f'DXVK-FF7R-FRAMES: present_id={i} count=256 mean_us=12000 p50_us=10000 p95_us=20000 p99_us=30000 max_us=40000'
                    for i in (1, 2, 3)
                ]
                lines.append(
                    'DXVK-FF7R-PIPELINES: samples=64 libraries=60 '
                    f'library_mean_us={library_mean} optimized=4 optimized_mean_us={optimized_mean} '
                    'over_10ms=0 over_33ms=0 queue_wait_samples=64 '
                    f'queue_wait_mean_us={queue_mean} queue_wait_over_10ms={over10} '
                    f'queue_wait_over_33ms={over33}'
                )
                path.write_text('\n'.join(lines), encoding='utf-8')

            capture(baseline, 12000, 8, 2, 300, 500)
            capture(candidate, 8000, 3, 1, 250, 450)
            result = perf.compare(baseline, candidate)

        self.assertTrue(result['benchmark_valid'])
        self.assertEqual(result['pipeline_queue_wait_mean_us_delta'], -4000)
        self.assertEqual(result['pipeline_queue_wait_over_10ms_delta'], -5)
        self.assertEqual(result['pipeline_queue_wait_over_33ms_delta'], -1)
        self.assertEqual(result['pipeline_queue_wait_samples_delta'], 0)
        self.assertEqual(result['pipeline_library_mean_us_delta'], -50)
        self.assertEqual(result['pipeline_optimized_mean_us_delta'], -50)
        self.assertIn('matched capture duration/workload', result['pipeline_note'])


    def test_pipeline_bind_snapshots_are_split_by_bind_point(self):
        with tempfile.TemporaryDirectory() as temp:
            baseline = Path(temp) / 'baseline.log'
            candidate = Path(temp) / 'candidate.log'
            baseline.write_text('\n'.join([
                'DXVK-FF7R-BINDS: point=graphics calls=1048576 skipped=100',
                'DXVK-FF7R-BINDS: point=compute calls=1048576 skipped=20',
            ]), encoding='utf-8')
            candidate.write_text('\n'.join([
                'DXVK-FF7R-BINDS: point=graphics calls=2097152 skipped=600',
                'DXVK-FF7R-BINDS: point=compute calls=2097152 skipped=70',
            ]), encoding='utf-8')
            parsed = perf.parse(candidate)
            result = perf.compare(baseline, candidate)

        self.assertEqual(parsed['pipeline_bind_latest_snapshots']['graphics']['skipped'], 600)
        self.assertEqual(parsed['pipeline_bind_latest_snapshots']['compute']['calls'], 2097152)
        self.assertEqual(result['pipeline_bind_deltas']['graphics']['calls_delta'], 1048576)
        self.assertEqual(result['pipeline_bind_deltas']['graphics']['skipped_delta'], 500)
        self.assertEqual(result['pipeline_bind_deltas']['compute']['skipped_delta'], 50)
        self.assertIn('matched capture durations', result['pipeline_bind_note'])


if __name__ == '__main__':
    unittest.main()
