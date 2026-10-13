"""Native host regression test for 256-sample FF7R DXGI Present metrics."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Ff7rPresentMetricsTest(unittest.TestCase):
    def test_steady_cadence_tail_and_suspend(self):
        code = r'''
#include "util_ff7r_metrics.h"
#include <cassert>
#include <chrono>
using namespace dxvk;
int main() {
  using namespace std::chrono;
  Ff7rPresentMetrics metrics;
  Ff7rPresentMetrics::Window window{};
  auto t = Ff7rPresentMetrics::Clock::time_point{};
  assert(!metrics.add(t, window));
  for (int i = 0; i != 256; ++i) {
    t += microseconds(i < 250 ? 33333 : 60000);
    assert(metrics.add(t, window) == (i == 255));
  }
  assert(window.p50Us == 33333 && window.p95Us == 33333);
  assert(window.p99Us == 60000 && window.maxUs == 60000);
  t += seconds(4); // Restart a fresh sample window after a long pause
  assert(!metrics.add(t, window));
  for (int i = 0; i != 256; ++i) {
    t += microseconds(16667);
    assert(metrics.add(t, window) == (i == 255));
  }
  assert(window.p50Us == 16667 && window.p99Us == 16667);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'test.cpp'
            executable = Path(tmp) / 'test'
            source.write_text(code)
            subprocess.run(['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror',
                            '-I', str(ROOT / 'src' / 'util'), str(source), '-o', str(executable)], check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    unittest.main()
