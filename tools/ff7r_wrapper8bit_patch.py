#!/usr/bin/env python3
"""Instrument pinned Android Vulkan wrapper to compare raw ICD and wrapper features.

Read only: never rewrite or force any Vulkan feature. Diagnostics execute only
when WRAPPER_FF7R_FEATURE_AUDIT=1. This compares the actual loaded underlying
ICD against the wrapper's existing Mesa-generated feature-table translation.
The reference source is pinned and source-anchored in the CI workflow.
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

      /* FF7R-8BIT: direct driver feature audit (read-only). The wrapper's normal
       * Mesa-generated wrapper_setup_device_features already queries the ICD.
       * Compare its result with a second raw query, without changing the
       * advertised feature table, extension table or CreateDevice flags.
       */
      if (getenv("WRAPPER_FF7R_FEATURE_AUDIT") &&
          atoi(getenv("WRAPPER_FF7R_FEATURE_AUDIT")) == 1) {
         VkPhysicalDeviceVulkan12Features ff7r_raw_12 = {
            .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES,
         };
         VkPhysicalDeviceFeatures2 ff7r_raw_features = {
            .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,
            .pNext = &ff7r_raw_12,
         };
         pdevice->dispatch_table.GetPhysicalDeviceFeatures2(
            pdevice->dispatch_handle, &ff7r_raw_features);

         WRAPPER_LOG(info,
            "FF7R-8BIT: raw_storage8=%u wrapper_storage8=%u "
            "raw_shaderInt8=%u wrapper_shaderInt8=%u "
            "raw_uniform8=%u wrapper_uniform8=%u "
            "raw_pushConstant8=%u wrapper_pushConstant8=%u",
            (unsigned)ff7r_raw_12.storageBuffer8BitAccess,
            (unsigned)supported_features->storageBuffer8BitAccess,
            (unsigned)ff7r_raw_12.shaderInt8,
            (unsigned)supported_features->shaderInt8,
            (unsigned)ff7r_raw_12.uniformAndStorageBuffer8BitAccess,
            (unsigned)supported_features->uniformAndStorageBuffer8BitAccess,
            (unsigned)ff7r_raw_12.storagePushConstant8,
            (unsigned)supported_features->storagePushConstant8);
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
    assert updated.index("pdevice->dispatch_table.GetPhysicalDeviceFeatures2(") < updated.index(
        "pdevice->base_supported_features = *supported_features;")
    assert not any(
        f"supported_features->{name} =" in PATCH for name in (
            "storageBuffer8BitAccess",
            "uniformAndStorageBuffer8BitAccess",
            "storagePushConstant8",
            "shaderInt8",
        )
    )
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
