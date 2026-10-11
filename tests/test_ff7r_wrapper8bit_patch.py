"""Regression coverage: read-only Vulkan wrapper feature audit and source drift."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ff7r_wrapper8bit_patch import patch, patch_instance, MARKER, INSTANCE_MARKER, LOAD_MARKER

FIXTURE = (
    "void wrapper_GetPhysicalDeviceFeatures2(void) {}\n"
    "void fake_init(void) {\n"
    "      wrapper_setup_device_features(pdevice);\n"
    "\n"
    "      struct vk_features *supported_features = &pdevice->vk.supported_features;\n"
    "      pdevice->base_supported_features = *supported_features;\n"
    "}\n"
)


class WrapperRawCapabilitiesTest(unittest.TestCase):
    def test_exact_anchor_and_idempotence(self):
        patched, status = patch(FIXTURE)
        self.assertEqual(status, "patched")
        self.assertIn(MARKER, patched)
        twice, second = patch(patched)
        self.assertEqual(second, "already-patched")
        self.assertEqual(twice, patched)

    def test_real_icd_query_streams_to_existing_wine_log(self):
        patched, _ = patch(FIXTURE)
        self.assertIn("pdevice->dispatch_table.GetPhysicalDeviceFeatures2(", patched)
        self.assertIn("pdevice->dispatch_handle, &ff7r_raw_features", patched)
        self.assertIn('raw_storage8=%u wrapper_storage8=%u', patched)
        self.assertIn("fprintf(stderr,", patched)
        self.assertIn("fflush(stderr);", patched)
        self.assertNotIn('getenv("WRAPPER_FF7R_FEATURE_AUDIT")', patched)

    def test_instance_startup_marker_and_idempotence(self):
        instance = (
            "static void *get_vulkan_handle() { return 0; }\n"
            "VKAPI_ATTR VkResult VKAPI_CALL\n"
            "wrapper_CreateInstance(void) {\n"
            "   struct wrapper_instance *instance;\n"
            "   VkResult result;\n"
            "\n"
            "   result = wrapper_vulkan_init();\n"
            "}\n"
        )
        updated, status = patch_instance(instance)
        self.assertEqual(status, "patched")
        self.assertIn(INSTANCE_MARKER, updated)
        self.assertIn(LOAD_MARKER, updated)
        self.assertIn('__attribute__((constructor))', updated)
        self.assertIn("fprintf(stderr,", updated)
        self.assertLess(updated.index(LOAD_MARKER), updated.index("static void *get_vulkan_handle()"))
        self.assertLess(updated.index(INSTANCE_MARKER),
                        updated.index("result = wrapper_vulkan_init();"))
        twice, status = patch_instance(updated)
        self.assertEqual(status, "already-patched")
        self.assertEqual(updated, twice)

    def test_instance_refuses_source_drift(self):
        with self.assertRaisesRegex(ValueError, "anchor"):
            patch_instance("void unrelated() {}")

    def test_capabilities_are_never_changed_by_probe(self):
        patched, _ = patch(FIXTURE)
        for name in (
            "storageBuffer8BitAccess", "uniformAndStorageBuffer8BitAccess",
            "storagePushConstant8", "shaderInt8",
        ):
            self.assertIn("ff7r_raw_12." + name, patched)
            self.assertIn("supported_features->" + name, patched)
            self.assertNotIn("supported_features->" + name + " =", patched)
        self.assertEqual(patched.count("pdevice->base_supported_features = *supported_features;"), 1)

    def test_feature_snapshot_preserved_after_audit(self):
        patched, _ = patch(FIXTURE)
        self.assertLess(
            patched.index("pdevice->dispatch_table.GetPhysicalDeviceFeatures2("),
            patched.index("pdevice->base_supported_features = *supported_features;"),
        )

    def test_refuses_drifted_or_ambiguous_sources(self):
        with self.assertRaisesRegex(ValueError, "anchor"):
            patch(FIXTURE.replace("wrapper_setup_device_features(pdevice);", "changed();"))
        with self.assertRaisesRegex(ValueError, "entrypoint"):
            patch(FIXTURE.replace("wrapper_GetPhysicalDeviceFeatures2", "removed"))
        with self.assertRaisesRegex(ValueError, "anchor"):
            patch(FIXTURE + FIXTURE)

    def test_log_contains_full_8bit_comparison(self):
        patched, _ = patch(FIXTURE)
        for name in ("storage8", "shaderInt8", "uniform8", "pushConstant8"):
            self.assertIn("raw_" + name + "=%u", patched)
            self.assertIn("wrapper_" + name + "=%u", patched)


if __name__ == "__main__":
    unittest.main()
