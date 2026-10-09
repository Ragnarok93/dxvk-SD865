#pragma once

#include <cstddef>
#include <cstdint>
#include <string_view>

// Header-only policy: intentionally independent of Vulkan and the DXVK runtime.
// This lets CI exercise device matching and compiler-worker selection without a GPU.
namespace dxvk::sd865 {

  constexpr uint32_t QualcommVendorId = 0x5143u;

  constexpr bool isAsciiAlphaNumeric(char c) {
    return (c >= '0' && c <= '9')
        || (c >= 'a' && c <= 'z')
        || (c >= 'A' && c <= 'Z');
  }

  constexpr char lowerAscii(char c) {
    return c >= 'A' && c <= 'Z' ? char(c - 'A' + 'a') : c;
  }

  constexpr bool matchesAt(std::string_view name, std::size_t offset, std::string_view token) {
    if (offset > name.size() || name.size() - offset < token.size())
      return false;

    for (std::size_t i = 0; i < token.size(); i++) {
      if (lowerAscii(name[offset + i]) != lowerAscii(token[i]))
        return false;
    }

    return true;
  }

  // Mesa/forks have used both "Turnip Adreno (TM) 650" and "Adreno 650".
  // Do not match "6500", "650X" or a different Adreno generation.
  constexpr bool hasAdreno650Name(std::string_view name) {
    for (std::size_t i = 0; i < name.size(); i++) {
      if (!matchesAt(name, i, "Adreno"))
        continue;

      if (i && isAsciiAlphaNumeric(name[i - 1]))
        continue;

      std::size_t end = i + 6u;
      if (end < name.size() && isAsciiAlphaNumeric(name[end]))
        continue;

      // Allow the optional "(TM)" and spacing between the GPU family and 650.
      for (std::size_t j = end; j < name.size() && j < end + 20u; j++) {
        if (matchesAt(name, j, "650")
         && (j == 0u || !isAsciiAlphaNumeric(name[j - 1u]))
         && (j + 3u == name.size() || !isAsciiAlphaNumeric(name[j + 3u])))
          return true;
      }
    }

    return false;
  }

  constexpr bool isTurnipQualcomm(uint32_t vendorId, uint32_t driverId, uint32_t turnipId) {
    return vendorId == QualcommVendorId && driverId == turnipId;
  }

  constexpr bool isTurnipAdreno650(uint32_t vendorId, uint32_t driverId,
                                   uint32_t turnipId, std::string_view name) {
    return isTurnipQualcomm(vendorId, driverId, turnipId) && hasAdreno650Name(name);
  }

  // Profile: -1 = auto, 0 = off, 1 = force for testing.
  // Forced activation still requires Qualcomm + Turnip; never enables on
  // a proprietary driver or another GPU vendor.
  constexpr bool isProfileActive(uint32_t vendorId, uint32_t driverId,
                                  uint32_t turnipId, std::string_view name, int32_t mode) {
    return mode != 0
        && isTurnipQualcomm(vendorId, driverId, turnipId)
        && (hasAdreno650Name(name) || mode > 0);
  }

  // The standard DXVK override ALWAYS wins. In auto mode, existing DXVK
  // behaviour is unchanged; an SD865 override is an explicit A/B experiment.
  constexpr uint32_t chooseCompilerWorkerCount(uint32_t availableCores,
                                                int32_t standardOverride,
                                                int32_t sd865Override,
                                                bool profileActive) {
    uint32_t result = availableCores ? availableCores : 1u;
    if (result > 64u)
      result = 64u;

    if (standardOverride > 0)
      return uint32_t(standardOverride);

    if (profileActive && sd865Override > 0)
      return sd865Override > 8 ? 8u : uint32_t(sd865Override);

    return result;
  }

}
