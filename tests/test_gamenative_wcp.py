"""Test GameNative content-profile paths before producing WCP packages."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package_gamenative_wcp import REQUIRED, stage_dxvk


class PackageTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.build = self.base / "build"
        self.stage = self.base / "stage"
        for arch in ("x64", "x32"):
            (self.build / arch).mkdir(parents=True)
            for name in REQUIRED:
                (self.build / arch / name).write_bytes(b"MZ")

    def test_targets_match_gamenative_trusted_list(self):
        profile = stage_dxvk(self.build, self.stage, "sd865-abc123")
        self.assertEqual(profile["type"], "DXVK")
        self.assertEqual(len(profile["files"]), 8)
        self.assertIn(
            {"source": "x64/d3d11.dll", "target": "${system32}/d3d11.dll"},
            profile["files"])
        self.assertIn(
            {"source": "x32/d3d9.dll", "target": "${syswow64}/d3d9.dll"},
            profile["files"])
        self.assertTrue((self.stage / "profile.json").is_file())

    def test_unknown_dll_excluded(self):
        (self.build / "x64" / "unknown.dll").write_bytes(b"MZ")
        self.assertEqual(len(stage_dxvk(self.build, self.stage, "sd865-x")["files"]), 8)

    def test_missing_arch_dll_rejected(self):
        (self.build / "x32" / "dxgi.dll").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required x32"):
            stage_dxvk(self.build, self.stage, "sd865-x")

    def test_traversal_invalid(self):
        with self.assertRaisesRegex(ValueError, "version"):
            stage_dxvk(self.build, self.stage, "../../escape")


if __name__ == "__main__":
    unittest.main()
