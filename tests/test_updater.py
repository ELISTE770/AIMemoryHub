# -*- coding: utf-8 -*-
"""
Tests for the auto-updater: version comparison, TLS hardening, and the installer
integrity check standing between a downloaded .exe and it being executed.

Run with:  python -m unittest discover -s tests
"""

import hashlib
import ssl
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import updater


class TestVersionParsing(unittest.TestCase):

    def test_parse_version(self):
        cases = [
            ("v6.2", (6, 2)),
            ("6.2", (6, 2)),
            ("V6.10.1", (6, 10, 1)),
            ("", (0,)),
            ("abc", (0,)),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(updater.parse_version(raw), expected)

    def test_version_ordering_is_numeric_not_lexicographic(self):
        # "6.10" must be newer than "6.9" - a string compare gets this backwards.
        self.assertGreater(updater.parse_version("6.10"), updater.parse_version("6.9"))


class TestTlsHardening(unittest.TestCase):

    def setUp(self):
        import os
        self._prev = os.environ.pop(updater.CA_BUNDLE_ENV, None)

    def tearDown(self):
        import os
        if self._prev is not None:
            os.environ[updater.CA_BUNDLE_ENV] = self._prev
        else:
            os.environ.pop(updater.CA_BUNDLE_ENV, None)

    def test_context_verifies_certificates_by_default(self):
        ctx = updater.build_ssl_context()
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED,
                         "certificate validation must never be disabled")
        self.assertTrue(ctx.check_hostname, "hostname checking must never be disabled")

    def test_invalid_ca_bundle_does_not_downgrade_verification(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            bogus = Path(d) / "proxy-ca.pem"
            bogus.write_text("not a certificate", encoding="utf-8")
            os.environ[updater.CA_BUNDLE_ENV] = str(bogus)

            ctx = updater.build_ssl_context()
            self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)
            self.assertTrue(ctx.check_hostname)


class TestInstallerIntegrity(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._real_popen = updater.subprocess.Popen
        self._real_exit = updater.os._exit

    def tearDown(self):
        updater.subprocess.Popen = self._real_popen
        updater.os._exit = self._real_exit
        self._tmp.cleanup()

    def test_sha256_of_file(self):
        f = self.tmp / "payload.bin"
        f.write_bytes(b"hello world")
        self.assertEqual(updater.sha256_of_file(str(f)),
                         hashlib.sha256(b"hello world").hexdigest())

    def test_extract_asset_sha256(self):
        digest = "a" * 64
        self.assertEqual(updater.extract_asset_sha256({"digest": f"sha256:{digest}"}), digest)
        self.assertIsNone(updater.extract_asset_sha256({"digest": "md5:abc"}))
        self.assertIsNone(updater.extract_asset_sha256({"digest": "sha256:tooshort"}))
        self.assertIsNone(updater.extract_asset_sha256({}))
        self.assertIsNone(updater.extract_asset_sha256(None))

    def test_tampered_installer_is_refused_and_deleted(self):
        """A swapped/corrupted installer must never reach subprocess.Popen."""
        fake_installer = self.tmp / "AIMemoryHub_Setup.exe"
        fake_installer.write_bytes(b"malicious payload")

        launched = []
        updater.subprocess.Popen = lambda *a, **k: launched.append(a)
        updater.os._exit = lambda code: self.fail("the app must not exit for a rejected installer")

        with self.assertRaises(ValueError):
            updater.launch_installer_and_exit(str(fake_installer), expected_sha256="b" * 64)

        self.assertEqual(launched, [], "a file failing the hash check must not be executed")
        self.assertFalse(fake_installer.exists(), "the rejected installer must be removed from disk")

    def test_verified_installer_is_launched(self):
        installer = self.tmp / "AIMemoryHub_Setup.exe"
        installer.write_bytes(b"genuine installer")
        good_hash = hashlib.sha256(b"genuine installer").hexdigest()

        launched, exited = [], []
        updater.subprocess.Popen = lambda *a, **k: launched.append(a)
        updater.os._exit = lambda code: exited.append(code)

        updater.launch_installer_and_exit(str(installer), expected_sha256=good_hash)

        self.assertTrue(launched, "a verified installer must be launched")
        self.assertEqual(exited, [0], "the app must exit so the installer can replace it")

    def test_download_rejects_hash_mismatch(self):
        dest = self.tmp / "setup.exe"

        class FakeResponse:
            headers = {"content-length": "5"}

            def __init__(self):
                self._chunks = [b"12345", b""]

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self, _size):
                return self._chunks.pop(0)

        real_urlopen = updater.urllib.request.urlopen
        updater.urllib.request.urlopen = lambda *a, **k: FakeResponse()
        try:
            ok, msg = updater.download_update(
                "https://example.invalid/setup.exe", str(dest), expected_sha256="c" * 64
            )
        finally:
            updater.urllib.request.urlopen = real_urlopen

        self.assertFalse(ok)
        self.assertIn("שלמות", msg)
        self.assertFalse(dest.exists(),
                         "a file failing verification must be deleted, not left on disk")


if __name__ == "__main__":
    unittest.main()
