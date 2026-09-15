"""
Security utilities for sensitive integration credentials.
"""

from cryptography.fernet import Fernet, InvalidToken

from backend.config import settings


def _get_fernet() -> Fernet:
    key = settings.INTEGRATION_ENCRYPTION_KEY

    if not key:
        raise RuntimeError(
            "INTEGRATION_ENCRYPTION_KEY is not configured."
        )

    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise RuntimeError(
            "INTEGRATION_ENCRYPTION_KEY is invalid."
        ) from exc


def encrypt_credentials(credentials: dict) -> str:
    """
    Encrypt an integration credentials dictionary.

    The encrypted result is returned as a string so it can
    safely be stored in the existing JSON database column.
    """

    import json

    plaintext = json.dumps(
        credentials,
        separators=(",", ":"),
    ).encode("utf-8")

    return _get_fernet().encrypt(plaintext).decode("utf-8")


def decrypt_credentials(encrypted_credentials) -> dict:
    """
    Decrypt integration credentials.

    Supports the new encrypted string format.
    Also accepts an existing dictionary for backward compatibility
    with integrations created before encryption was enabled.
    """

    import json

    # Existing legacy records may still contain plaintext JSON.
    if isinstance(encrypted_credentials, dict):
        return encrypted_credentials

    if not encrypted_credentials:
        return {}

    if not isinstance(encrypted_credentials, str):
        raise ValueError("Invalid encrypted credentials format.")

    try:
        plaintext = _get_fernet().decrypt(
            encrypted_credentials.encode("utf-8")
        )

        data = json.loads(plaintext.decode("utf-8"))

        if not isinstance(data, dict):
            raise ValueError("Decrypted credentials must be a dictionary.")

        return data

    except InvalidToken as exc:
        raise ValueError(
            "Unable to decrypt integration credentials."
        ) from exc


def credentials_are_encrypted(credentials) -> bool:
    """
    Return True when credentials are stored in the new encrypted format.
    """

    return isinstance(credentials, str) and bool(credentials)