"""Test GameNative content-profile paths before producing WCP packages."""
import sys
import tempfile
import tarfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from package_gamenative_wcp import REQUIRED, stage_dxvk, write_tar, validate_gamenative_tar


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

    def test_archive_has_directories_before_dlls(self):
        stage_dxvk(self.build, self.stage, "sd865-x")
        tar_path = self.base / "valid.tar"
        write_tar(self.stage, tar_path)
        with tarfile.open(tar_path, "r") as tar:
            members = list(tar)
        names = [m.name.rstrip("/") for m in members]
        self.assertEqual(names[0], "profile.json")
        self.assertIn("x32", names)
        self.assertIn("x64", names)
        self.assertTrue(members[names.index("x32")].isdir())
        self.assertTrue(members[names.index("x64")].isdir())
        self.assertLess(names.index("x32"), names.index("x32/d3d11.dll"))
        self.assertLess(names.index("x64"), names.index("x64/d3d11.dll"))

    def test_missing_directory_entries_regression(self):
        # Reproduce the old tar format: file entries but no x32/ or x64/
        # entries. GameNative fails to create the DLLs' parent directories.
        stage_dxvk(self.build, self.stage, "sd865-x")
        broken = self.base / "broken.tar"
        with tarfile.open(broken, "w") as tar:
            for path in sorted(self.stage.rglob("*")):
                if path.is_file():
                    tar.add(path, arcname=path.relative_to(self.stage).as_posix())
        with self.assertRaisesRegex(ValueError, "Missing parent directory entry"):
            validate_gamenative_tar(broken)

    def test_traversal_invalid(self):
        with self.assertRaisesRegex(ValueError, "version"):
            stage_dxvk(self.build, self.stage, "../../escape")


if __name__ == "__main__":
    unittest.main()
