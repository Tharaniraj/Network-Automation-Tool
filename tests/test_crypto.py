"""
Unit tests for modules/crypto.py
"""

import tempfile
import unittest
from pathlib import Path
from unittest import skipUnless

try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

from modules.crypto import CredentialVault, get_vault


@skipUnless(CRYPTO_AVAILABLE, "cryptography library not installed")
class TestCredentialVault(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # Point the vault at a temp directory so tests don't touch data/.key
        CredentialVault.KEY_FILE = Path(self.tmp.name) / ".key"

    def tearDown(self):
        self.tmp.cleanup()
        # Reset to default so other tests/modules are unaffected
        CredentialVault.KEY_FILE = Path("data/.key")

    def _vault(self) -> CredentialVault:
        return CredentialVault()

    def test_encrypt_decrypt_roundtrip(self):
        v = self._vault()
        plaintext = "supersecret"
        encrypted = v.encrypt(plaintext)
        self.assertNotEqual(encrypted, plaintext)
        self.assertEqual(v.decrypt(encrypted), plaintext)

    def test_encrypt_empty_string(self):
        v = self._vault()
        self.assertEqual(v.encrypt(""), "")

    def test_decrypt_empty_string(self):
        v = self._vault()
        self.assertEqual(v.decrypt(""), "")

    def test_no_double_encryption(self):
        """Calling encrypt twice on an already-encrypted value returns same token."""
        v = self._vault()
        once = v.encrypt("password")
        twice = v.encrypt(once)
        self.assertEqual(once, twice)

    def test_legacy_plaintext_passthrough(self):
        """A plaintext value that is not a Fernet token decrypts unchanged."""
        v = self._vault()
        legacy = "plaintext_password"
        result = v.decrypt(legacy)
        self.assertEqual(result, legacy)

    def test_key_persisted(self):
        """Second vault instance reuses the same key (can decrypt first vault's tokens)."""
        v1 = self._vault()
        encrypted = v1.encrypt("hello")
        v2 = self._vault()
        self.assertEqual(v2.decrypt(encrypted), "hello")

    def test_key_file_created(self):
        self._vault()
        self.assertTrue(CredentialVault.KEY_FILE.exists())

    def test_available_property(self):
        v = self._vault()
        self.assertTrue(v.available)


class TestVaultUnavailable(unittest.TestCase):
    """Behaviour when cryptography is not installed (simulated via monkey-patch)."""

    def test_encrypt_returns_plaintext_when_unavailable(self):
        import modules.crypto as crypto_module
        original = crypto_module.CRYPTO_AVAILABLE
        crypto_module.CRYPTO_AVAILABLE = False
        try:
            v = CredentialVault()
            self.assertEqual(v.encrypt("password"), "password")
            self.assertEqual(v.decrypt("password"), "password")
        finally:
            crypto_module.CRYPTO_AVAILABLE = original


if __name__ == "__main__":
    unittest.main()
