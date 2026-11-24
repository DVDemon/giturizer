import pytest
from cryptography.fernet import InvalidToken

from archdiscovery.crypto import TokenCipher


def test_encrypt_decrypt_roundtrip() -> None:
    cipher = TokenCipher("test-secret")
    encrypted = cipher.encrypt("glpat-secret")
    assert encrypted != "glpat-secret"
    assert cipher.decrypt(encrypted) == "glpat-secret"


def test_different_secrets_cannot_decrypt() -> None:
    first = TokenCipher("secret-one")
    second = TokenCipher("secret-two")
    encrypted = first.encrypt("value")
    with pytest.raises(InvalidToken):
        second.decrypt(encrypted)
