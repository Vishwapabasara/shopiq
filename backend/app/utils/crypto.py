from cryptography.fernet import Fernet
from app.config import settings


def _get_fernet() -> Fernet:
    key = settings.TOKEN_ENCRYPTION_KEY
    if not key:
        # Dev fallback — generate a temporary key (DO NOT use in production)
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(token: str) -> str:
    """Encrypt a Shopify access token for storage."""
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt a stored Shopify access token."""
    return _get_fernet().decrypt(encrypted.encode()).decode()
