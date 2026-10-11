"""Regression coverage: read-only Vulkan wrapper feature audit and source drift."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ff7r_wrapper8bit_patch import patch, MARKER

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

    def test_direct_icd_query_only_when_opted_in(self):
        patched, _ = patch(FIXTURE)
        guard = patched.index('getenv("WRAPPER_FF7R_FEATURE_AUDIT")')
        raw_query = patched.index("pdevice->dispatch_table.GetPhysicalDeviceFeatures2(")
        self.assertLess(guard, raw_query)
        self.assertIn("pdevice->dispatch_handle, &ff7r_raw_features", patched)
        self.assertIn('raw_storage8=%u wrapper_storage8=%u', patched)

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
