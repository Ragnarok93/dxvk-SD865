"""Guard the FF7R wrapper feature-repair against blind capability spoofing."""
import sys
import tempfile
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
    def test_patch_is_exact_and_idempotent(self):
        patched, status = patch(FIXTURE)
        self.assertEqual(status, "patched")
        self.assertIn(MARKER, patched)
        twice, second_status = patch(patched)
        self.assertEqual(second_status, "already-patched")
        self.assertEqual(twice, patched)

    def test_gates_on_real_driver_feature_query(self):
        patched, _ = patch(FIXTURE)
        self.assertIn("pdevice->dispatch_table.GetPhysicalDeviceFeatures2(", patched)
        self.assertIn("pdevice->dispatch_handle, &ff7r_raw_features", patched)
        for feature in (
            "storageBuffer8BitAccess",
            "uniformAndStorageBuffer8BitAccess",
            "storagePushConstant8",
            "shaderInt8",
        ):
            self.assertIn(
                f"supported_features->{feature} = ff7r_raw_12.{feature};",
                patched,
            )
            self.assertNotIn(f"supported_features->{feature} = true;", patched)

    def test_original_feature_snapshot_is_after_driver_query(self):
        patched, _ = patch(FIXTURE)
        self.assertLess(
            patched.index("GetPhysicalDeviceFeatures2("),
            patched.index("pdevice->base_supported_features = *supported_features;"),
        )

    def test_rejects_moved_anchor_or_unreviewed_source(self):
        with self.assertRaisesRegex(ValueError, "anchor"):
            patch(FIXTURE.replace("wrapper_setup_device_features(pdevice);", "changed();"))
        with self.assertRaisesRegex(ValueError, "entrypoint"):
            patch(FIXTURE.replace("wrapper_GetPhysicalDeviceFeatures2", "removed"))

    def test_rejects_ambiguous_multiple_anchors(self):
        with self.assertRaisesRegex(ValueError, "anchor"):
            patch(FIXTURE + FIXTURE)

    def test_diagnostics_opt_in_is_explicit(self):
        patched, _ = patch(FIXTURE)
        self.assertIn('WRAPPER_FF7R_FEATURE_AUDIT', patched)
        self.assertIn("host_storage8=%u wrapper_previous_storage8=%u", patched)


if __name__ == "__main__":
    unittest.main()
