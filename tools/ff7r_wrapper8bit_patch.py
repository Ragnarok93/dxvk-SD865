#!/usr/bin/env python3
"""Patch the pinned GameNative Vulkan wrapper to preserve *real* driver 8-bit features.

Unlike unconditional DXVK capability fakes, this reads vkGetPhysicalDeviceFeatures2
from the underlying Vulkan ICD. It only advertises flags the underlying driver
actually returns. Maintains native base_supported_features before wrapper overrides.

Source family: leegao/mesa-wrapper-CI@gn_wrapper2, pinned in the CI workflow.
This file is a source patcher, NOT a runtime feature override for DXVK itself.
"""
import argparse
from pathlib import Path

RELATIVE_SOURCE = Path("src/vulkan/wrapper/wrapper_physical_device.c")
MARKER = "FF7R-8BIT: direct driver feature audit"
ANCHOR = """      wrapper_setup_device_features(pdevice);

      struct vk_features *supported_features = &pdevice->vk.supported_features;
      pdevice->base_supported_features = *supported_features;"""
PATCH = """      wrapper_setup_device_features(pdevice);

      struct vk_features *supported_features = &pdevice->vk.supported_features;

      /* FF7R-8BIT: direct driver feature audit. Mesa wrapper feature copying
       * can omit Vulkan 1.2 / VK_KHR_8bit_storage fields even when the host
       * Turnip ICD supports them. Ask the underlying ICD, NOT the wrapper
       * feature table. Never invent a shader/storage capability.
       *
       * The wrapper's base_supported_features MUST capture these real bits:
       * the underlying vkCreateDevice request receives them unchanged.
       */
      VkPhysicalDeviceVulkan12Features ff7r_raw_12 = {
         .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES,
      };
      VkPhysicalDeviceFeatures2 ff7r_raw_features = {
         .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,
         .pNext = &ff7r_raw_12,
      };
      pdevice->dispatch_table.GetPhysicalDeviceFeatures2(
         pdevice->dispatch_handle, &ff7r_raw_features);

      const VkBool32 ff7r_pre_storage = supported_features->storageBuffer8BitAccess;
      const VkBool32 ff7r_pre_shader = supported_features->shaderInt8;
      supported_features->storageBuffer8BitAccess = ff7r_raw_12.storageBuffer8BitAccess;
      supported_features->uniformAndStorageBuffer8BitAccess =
         ff7r_raw_12.uniformAndStorageBuffer8BitAccess;
      supported_features->storagePushConstant8 = ff7r_raw_12.storagePushConstant8;
      supported_features->shaderInt8 = ff7r_raw_12.shaderInt8;

      if (getenv("WRAPPER_FF7R_FEATURE_AUDIT") &&
          atoi(getenv("WRAPPER_FF7R_FEATURE_AUDIT")) == 1) {
         WRAPPER_LOG(info,
            "FF7R-8BIT: host_storage8=%u wrapper_previous_storage8=%u "
            "host_shaderInt8=%u wrapper_previous_shaderInt8=%u "
            "host_uniform8=%u host_pushConstant8=%u",
            (unsigned)ff7r_raw_12.storageBuffer8BitAccess,
            (unsigned)ff7r_pre_storage,
            (unsigned)ff7r_raw_12.shaderInt8,
            (unsigned)ff7r_pre_shader,
            (unsigned)ff7r_raw_12.uniformAndStorageBuffer8BitAccess,
            (unsigned)ff7r_raw_12.storagePushConstant8);
      }

      pdevice->base_supported_features = *supported_features;"""


def patch(source: str) -> tuple[str, str]:
    if MARKER in source:
        if source.count(MARKER) != 1 or "ff7r_raw_12.storageBuffer8BitAccess" not in source:
            raise ValueError("Existing patch looks modified or incomplete")
        return source, "already-patched"
    if source.count(ANCHOR) != 1:
        raise ValueError("Expected wrapper initialization anchor was not found exactly once; inspect upstream")
    # Reject unreviewed or structurally changed wrapper sources.
    if "wrapper_GetPhysicalDeviceFeatures2" not in source:
        raise ValueError("Wrapper feature-query entrypoint not present; inspect upstream changes")
    updated = source.replace(ANCHOR, PATCH, 1)
    assert updated.count("pdevice->base_supported_features = *supported_features;") == 1
    assert updated.index("ff7r_raw_12.storageBuffer8BitAccess") < updated.index(
        "pdevice->base_supported_features = *supported_features;")
    return updated, "patched"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true", help="Validate without modifying files")
    args = parser.parse_args()
    path = args.source_root / RELATIVE_SOURCE
    original = path.read_text(encoding="utf-8")
    updated, status = patch(original)
    if not args.check and updated != original:
        path.write_text(updated, encoding="utf-8")
    print(f"{status}: {path}; {'unchanged (check)' if args.check else 'written or already-patched'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
