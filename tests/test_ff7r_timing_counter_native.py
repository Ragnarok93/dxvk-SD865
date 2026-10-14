"""Host test for the optional DXVK FF7R CPU phase aggregator."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Ff7rTimingCounterTest(unittest.TestCase):
    def test_aggregate_and_parallel_updates(self):
        source_code = r'''
#include "util_ff7r_timing.h"
#include <cassert>
#include <thread>
using namespace dxvk;
int main() {
  Ff7rTimingCounter stats(64);
  assert(stats.record(800));
  assert(!stats.record(15000));
  assert(!stats.record(41000));
  auto a = stats.snapshot();
  assert(a.count == 3 && a.maxUs == 41000);
  assert(a.over10ms == 2 && a.over33ms == 1);
  assert(a.meanUs == (800 + 15000 + 41000) / 3);
  for (int i = 3; i < 64; i++)
    assert(stats.record(100) == (i == 63));
  assert(stats.snapshot().count == 64);
  assert(Ff7rTimingCounter::timeUs(Ff7rTimingCounter::Clock::now()) > 0);

  Ff7rTimingCounter reduced, invalid(0), invalidNonPower(65);
  int reports = 0;
  for (int i = 0; i < 4096; i++) {
    reports += reduced.record(12000);
    assert(invalid.record(12000) == (i == 0 || ((i + 1) % 1024 == 0)));
    assert(invalidNonPower.record(12000) == (i == 0 || ((i + 1) % 1024 == 0)));
  }
  assert(reports == 5 && reduced.snapshot().count == 4096);
  assert(reduced.snapshot().meanUs == 12000);
  assert(reduced.snapshot().over10ms == 4096);
  Ff7rTimingCounter concurrently;
  auto task = [&concurrently] {
    for (int i = 0; i < 2048; ++i)
      concurrently.record(10000);
  };
  std::thread a_thread(task), b_thread(task);
  a_thread.join(); b_thread.join();
  auto b = concurrently.snapshot();
  assert(b.count == 4096 && b.maxUs == 10000);
  assert(b.meanUs == 10000 && b.over10ms == 4096 && b.over33ms == 0);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'test.cpp'
            executable = Path(tmp) / 'test'
            source.write_text(source_code)
            subprocess.run(
                ['c++', '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pthread',
                 '-I', str(ROOT / 'src' / 'util'), str(source), '-o', str(executable)],
                check=True)
            subprocess.run([str(executable)], check=True)


if __name__ == '__main__':
    unittest.main()
