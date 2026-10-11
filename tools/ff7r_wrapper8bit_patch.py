#!/usr/bin/env python3
"""Instrument pinned Android Vulkan wrapper to compare raw ICD and wrapper features.

Read only: never rewrite or force a Vulkan feature. This explicitly labeled
experimental WCP emits early-startup and actual raw-versus-wrapper feature
markers to stderr, which GameNative's built-in Wine log captures on Android.
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

      /* FF7R-8BIT: direct driver feature audit (read-only). This specialized
       * diagnostic WCP emits exactly one line per physical device directly
       * to stderr: GameNative captures stderr in its built-in Wine debug log.
       * No special WRAPPER_* variables, ADB, root or log-file permissions.
       * Do not modify the normal feature table, extensions or CreateDevice.
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

      fprintf(stderr,
         "FF7R-8BIT: raw_storage8=%u wrapper_storage8=%u "
         "raw_shaderInt8=%u wrapper_shaderInt8=%u "
         "raw_uniform8=%u wrapper_uniform8=%u "
         "raw_pushConstant8=%u wrapper_pushConstant8=%u\\n",
         (unsigned)ff7r_raw_12.storageBuffer8BitAccess,
         (unsigned)supported_features->storageBuffer8BitAccess,
         (unsigned)ff7r_raw_12.shaderInt8,
         (unsigned)supported_features->shaderInt8,
         (unsigned)ff7r_raw_12.uniformAndStorageBuffer8BitAccess,
         (unsigned)supported_features->uniformAndStorageBuffer8BitAccess,
         (unsigned)ff7r_raw_12.storagePushConstant8,
         (unsigned)supported_features->storagePushConstant8);
      fflush(stderr);

      pdevice->base_supported_features = *supported_features;"""

INSTANCE_PATH = Path("src/vulkan/wrapper/wrapper_instance.c")
LOAD_MARKER = "FF7R-8BIT: wrapper_library_loaded"
LOAD_ANCHOR = "static void *get_vulkan_handle()"
LOAD_PATCH = """/* FF7R-8BIT: diagnostic library-load marker, before Vulkan API entrypoints.
 * Logs once per actual .so load even if the game never calls vkCreateInstance.
 * Does not initialize the ICD or change any runtime Vulkan feature.
 */
__attribute__((constructor))
static void ff7r_wrapper_library_probe(void)
{
   fprintf(stderr, "FF7R-8BIT: wrapper_library_loaded\\n");
   fflush(stderr);
}

static void *get_vulkan_handle()"""
INSTANCE_MARKER = "FF7R-8BIT: wrapper_instance_probe"
INSTANCE_ANCHOR = """   struct wrapper_instance *instance;
   VkResult result;

   result = wrapper_vulkan_init();"""
INSTANCE_PATCH = """   struct wrapper_instance *instance;
   VkResult result;

   /* FF7R-8BIT: early wrapper provenance, before ICD instance initialization.
    * Only this explicitly labeled diagnostic wrapper emits this once per
    * vkCreateInstance. It goes into GameNative's existing Wine log exporter.
    */
   fprintf(stderr, "FF7R-8BIT: wrapper_instance_probe\\n");
   fflush(stderr);

   result = wrapper_vulkan_init();"""


def patch_instance(source: str) -> tuple[str, str]:
    if INSTANCE_MARKER in source or LOAD_MARKER in source:
        if source.count(INSTANCE_MARKER) != 1 or source.count(LOAD_MARKER) != 1:
            raise ValueError("Missing, duplicate or altered instance/library audit marker")
        return source, "already-patched"
    if source.count(INSTANCE_ANCHOR) != 1:
        raise ValueError("Expected Vulkan instance anchor not found exactly once")
    if source.count(LOAD_ANCHOR) != 1:
        raise ValueError("Expected wrapper-library load anchor not found exactly once")
    updated = source.replace(LOAD_ANCHOR, LOAD_PATCH, 1)
    updated = updated.replace(INSTANCE_ANCHOR, INSTANCE_PATCH, 1)
    assert updated.count(LOAD_MARKER) == 1
    assert updated.count(INSTANCE_MARKER) == 1
    return updated, "patched"


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
    assert 'fprintf(stderr,' in PATCH
    assert 'fflush(stderr);' in PATCH
    return updated, "patched"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument("--check", action="store_true", help="Validate without modifying files")
    args = parser.parse_args()
    for relative, patcher in (
        (RELATIVE_SOURCE, patch),
        (INSTANCE_PATH, patch_instance),
    ):
        path = args.source_root / relative
        original = path.read_text(encoding="utf-8")
        updated, status = patcher(original)
        if not args.check and updated != original:
            path.write_text(updated, encoding="utf-8")
        print(f"{status}: {path}; {'unchanged (check)' if args.check else 'written or already-patched'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
