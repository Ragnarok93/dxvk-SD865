"""No conclusions from missing/conflicting probe logs or unverified 8-bit reports."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ff7r_turnip8_audit import analyze


def row(raw=0, wrapped=0):
    return (
        "[info] FF7R-8BIT: raw_storage8=%d wrapper_storage8=%d "
        "raw_shaderInt8=1 wrapper_shaderInt8=1 "
        "raw_uniform8=0 wrapper_uniform8=0 "
        "raw_pushConstant8=0 wrapper_pushConstant8=0"
    ) % (raw, wrapped)


class Turnip8AuditTests(unittest.TestCase):
    def test_uninstrumented_capture_cannot_establish_raw_driver_support(self):
        x = analyze(["Device does not support required feature 'storageBuffer8BitAccess'"])
        self.assertEqual(x["verdict"], "no_valid_audit_marker")
        self.assertIsNone(x["raw_features"])
        self.assertEqual(x["dxvk_rejected_features"], ["storageBuffer8BitAccess"])

    def test_raw_storage_false_and_wrapper_false(self):
        self.assertEqual(analyze([row()])["verdict"], "driver_reports_storage8_unavailable")

    def test_wrapper_drops_supported_raw_storage(self):
        self.assertEqual(analyze([row(raw=1)])["verdict"], "raw_wrapper_feature_mismatch")

    def test_both_true_not_full_dxvk_compliance(self):
        self.assertEqual(analyze([row(raw=1, wrapped=1)])["verdict"],
                         "both_report_storage8_available_not_conformance_proof")

    def test_conflicting_sessions_fail_closed(self):
        self.assertEqual(analyze([row(), row(1, 1)])["verdict"],
                         "conflicting_driver_or_session_results")

    def test_repeated_matching_sample_is_ok(self):
        a = analyze([row(), row()])
        self.assertEqual(a["verdict"], "driver_reports_storage8_unavailable")
        self.assertEqual(a["marker_count"], 2)

    def test_invalid_flag_cannot_be_interpreted_as_true(self):
        self.assertEqual(analyze([row(2, 1)])["verdict"], "no_valid_audit_marker")

    def test_non_storage_flags_mismatch_is_reported(self):
        self.assertEqual(analyze([row().replace("wrapper_shaderInt8=1", "wrapper_shaderInt8=0")])["verdict"],
                         "raw_wrapper_feature_mismatch")


if __name__ == "__main__":
    unittest.main()
