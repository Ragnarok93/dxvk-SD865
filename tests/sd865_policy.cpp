#include <cassert>
#include <cstdint>
#include "../src/dxvk/dxvk_sd865.h"

using namespace dxvk::sd865;

static_assert(isTurnipAdreno650(0x5143u, 7u, 7u, "Turnip Adreno (TM) 650"));
static_assert(isTurnipAdreno650(0x5143u, 7u, 7u, "Adreno 650"));
static_assert(isTurnipAdreno650(0x5143u, 7u, 7u, "turnip adreno (tm) 650 (optimized)"));
static_assert(!isTurnipAdreno650(0x5143u, 7u, 7u, "Turnip Adreno (TM) 660"));
static_assert(!isTurnipAdreno650(0x5143u, 7u, 7u, "Adreno 6500"));
static_assert(!isTurnipAdreno650(0x5143u, 7u, 7u, "Adreno 650X"));
static_assert(!isTurnipAdreno650(0x5143u, 7u, 7u, "Adreno650")); // require GPU token boundaries
static_assert(!isTurnipAdreno650(0x5143u, 7u, 7u, "Adreno 730"));
static_assert(!isTurnipAdreno650(0x1234u, 7u, 7u, "Adreno 650"));
static_assert(!isTurnipAdreno650(0x5143u, 8u, 7u, "Adreno 650"));
static_assert(isProfileActive(0x5143u, 7u, 7u, "Adreno 650", -1));
static_assert(!isProfileActive(0x5143u, 7u, 7u, "Adreno 650", 0));
static_assert(isProfileActive(0x5143u, 7u, 7u, "Unknown Qualcomm GPU", 1));
static_assert(!isProfileActive(0x5143u, 8u, 7u, "Unknown Qualcomm GPU", 1));
static_assert(!isProfileActive(0x1234u, 7u, 7u, "Unknown Qualcomm GPU", 1));
static_assert(!isProfileActive(0x5143u, 7u, 7u, "Unknown Qualcomm GPU", -1));
static_assert(isFF7RemakeExecutable("FF7Remake_.exe"));
static_assert(isFF7RemakeExecutable("ff7remake_.EXE"));
static_assert(isFF7RemakeExecutable("ff7remake.exe"));
static_assert(!isFF7RemakeExecutable("ff7remake_.exe.bak"));
static_assert(!isFF7RemakeExecutable("ff7remake-helper.exe"));
static_assert(!isFF7RemakeExecutable("ff7remake_.exe_other"));
static_assert(!isFF7RemakeExecutable("kingdomhearts3.exe"));
static_assert(ff7RemakeWorkerOverride(0, 0, true, true, true) == 2);
static_assert(ff7RemakeWorkerOverride(4, 0, true, true, true) == 0);
static_assert(ff7RemakeWorkerOverride(0, 3, true, true, true) == 0);
static_assert(ff7RemakeWorkerOverride(0, 0, false, true, true) == 0);
static_assert(ff7RemakeWorkerOverride(0, 0, true, false, true) == 0);
static_assert(ff7RemakeWorkerOverride(0, 0, true, true, false) == 0);
static_assert(sanitizeStatsInterval(-20) == 0u);
static_assert(sanitizeStatsInterval(0) == 0u);
static_assert(sanitizeStatsInterval(1) == 60u);
static_assert(sanitizeStatsInterval(300) == 300u);
static_assert(sanitizeStatsInterval(10000) == 3600u);
static_assert(chooseCompilerWorkerCount(8u, 0, 0, true) == 8u);
static_assert(chooseCompilerWorkerCount(8u, 0, 3, true) == 3u);
static_assert(chooseCompilerWorkerCount(8u, 2, 3, true) == 2u);
static_assert(chooseCompilerWorkerCount(8u, 0, 3, false) == 8u);
static_assert(chooseCompilerWorkerCount(8u, 0, 99, true) == 8u);
static_assert(chooseCompilerWorkerCount(0u, 0, 0, true) == 1u);
static_assert(chooseCompilerWorkerCount(128u, 0, 0, true) == 64u);

int main() {
  assert(isTurnipAdreno650(0x5143u, 7u, 7u, "Adreno (TM) 650"));
  assert(!isTurnipAdreno650(0x5143u, 7u, 7u, "Adreno 6500 overclocked"));
  assert(chooseCompilerWorkerCount(8u, 0, -1, true) == 8u);
  return 0;
}
