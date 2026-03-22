"""
Credential encryption module using Fernet symmetric encryption.
Passwords are encrypted at rest in devices.json.
"""

import os
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

_FERNET_PREFIX = b"gAAAAA"


class CredentialVault:
    """Handles encryption/decryption of device credentials using Fernet."""

    KEY_FILE = Path("data/.key")

    def __init__(self):
        if CRYPTO_AVAILABLE:
            self._fernet = Fernet(self._load_or_create_key())
        else:
            self._fernet = None

    def _load_or_create_key(self) -> bytes:
        """Load the key from disk, generating a new one on first run."""
        self.KEY_FILE.parent.mkdir(exist_ok=True)
        if self.KEY_FILE.exists():
            return self.KEY_FILE.read_bytes()
        key = Fernet.generate_key()
        self.KEY_FILE.write_bytes(key)
        # Restrict file permissions on Unix/macOS
        try:
            os.chmod(self.KEY_FILE, 0o600)
        except Exception:
            pass
        return key

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string. Returns plaintext unchanged if crypto unavailable."""
        if not CRYPTO_AVAILABLE or not self._fernet or not plaintext:
            return plaintext
        # Already encrypted — don't double-encrypt
        if plaintext.encode().startswith(_FERNET_PREFIX):
            return plaintext
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt a Fernet ciphertext string.
        If the value is legacy plaintext, it is returned as-is.
        """
        if not CRYPTO_AVAILABLE or not self._fernet or not ciphertext:
            return ciphertext
        # Not a Fernet token — treat as legacy plaintext
        if not ciphertext.encode().startswith(_FERNET_PREFIX):
            return ciphertext
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except (InvalidToken, Exception):
            return ciphertext

    @property
    def available(self) -> bool:
        """True if the cryptography library is installed."""
        return CRYPTO_AVAILABLE


# Module-level singleton
_vault: "CredentialVault | None" = None


def get_vault() -> CredentialVault:
    """Return the global CredentialVault instance."""
    global _vault
    if _vault is None:
        _vault = CredentialVault()
    return _vault
