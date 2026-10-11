"""Phase-0 log attribution regression tests: don't infer API from mere DLL loading."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from ff7r_phase0_report import classify


class AttributionTests(unittest.TestCase):
    D = "info: DXVK-FF7R-PHASE0: d3d11_device_created exe=FF7Remake_.exe feature_level=11_0"
    P11 = "info: DXVK-FF7R-PHASE0: first_dxgi_present exe=FF7Remake_.exe d3d12_queue=0 sync_interval=0"
    P12 = "info: DXVK-FF7R-PHASE0: first_dxgi_present exe=FF7Remake_.exe d3d12_queue=1 sync_interval=0"
    F = "I ABC FEX-FF7R-PHASE0: backend=ARM64EC app=FF7Remake_.exe pid=123 wine=1"

    def test_dx11_requires_device_and_present(self):
        r = classify([self.D, self.P11, self.F])
        self.assertEqual(r["api_evidence"], "d3d11_dxvk_present_path")
        self.assertEqual(r["fex_backends"], ["ARM64EC"])

    def test_d3d12_dxgi_does_not_imply_dxvk_d3d12(self):
        r = classify([self.P12, self.F])
        self.assertEqual(r["api_evidence"], "d3d12_dxgi_present_path")
        self.assertEqual(r["d3d11_device_events"], 0)

    def test_d3d12_with_d3d11_device_is_still_d3d12_present(self):
        self.assertEqual(classify([self.D, self.P12])["api_evidence"], "d3d12_dxgi_present_path")

    def test_dll_load_not_confirmation(self):
        self.assertEqual(classify(["Loaded d3d11.dll", "DXVK 2.7.1"])["api_evidence"], "unverified")

    def test_device_only_not_rendering_proof(self):
        self.assertEqual(classify([self.D])["api_evidence"], "d3d11_device_only_no_present")

    def test_present_without_device_stays_ambiguous(self):
        self.assertEqual(classify([self.P11])["api_evidence"], "dxgi_present_no_d3d11_device_evidence")

    def test_mixed_sessions_fail_closed(self):
        self.assertEqual(classify([self.P11, self.P12, self.D])["api_evidence"], "mixed_or_ambiguous")

    def test_other_exe_ignored(self):
        r = classify([
            self.D.replace("FF7Remake_.exe", "Unrelated.exe"),
            self.P12.replace("FF7Remake_.exe", "Unrelated.exe"),
            self.F.replace("FF7Remake_.exe", "explorer.exe")
        ])
        self.assertEqual(r["api_evidence"], "unverified")
        self.assertEqual(r["fex_backends"], [])


if __name__ == "__main__":
    unittest.main()
