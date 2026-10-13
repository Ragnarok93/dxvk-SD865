"""Execute DXVK's refresh arithmetic with a minimal D3D color type stub."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RefreshStatisticsTests(unittest.TestCase):
    def test_valid_and_unavailable_display_refresh(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / "d3d9types.h").write_text("using D3DCOLOR = unsigned int;\n")
            source = tmp / "refresh.cpp"
            source.write_text(r'''
#include <chrono>
#include <cstdint>
#include <cassert>
#include "src/util/util_misc.h"
int main() {
  using namespace std::chrono;
  assert(dxvk::computeRefreshPeriod(60, 1).count() == 16666666);
  assert(dxvk::computeRefreshPeriod(120, 1).count() == 8333333);
  assert(dxvk::computeRefreshPeriod(60000, 1001).count() == 16683333);
  assert(dxvk::computeRefreshPeriod(0, 1).count() == 0);
  assert(dxvk::computeRefreshPeriod(60, 0).count() == 0);
  auto t0 = steady_clock::time_point{};
  auto t1 = t0 + seconds(1);
  assert(dxvk::computeRefreshCount(t0, t1, nanoseconds(0)) == 0);
  assert(dxvk::computeRefreshCount(t1, t0, nanoseconds(10000000)) == 0);
  assert(dxvk::computeRefreshCount(t0, t1, nanoseconds(10000000)) == 100);
}
''')
            binary = tmp / "refresh"
            subprocess.run(["g++", "-std=c++17", "-I", str(tmp), "-I", str(ROOT),
                            str(source), "-o", str(binary)], check=True,
                           capture_output=True, text=True)
            subprocess.run([str(binary)], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
