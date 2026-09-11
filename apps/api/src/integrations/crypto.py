"""Cryptographic service for OAuth tokens at-rest encryption using AES-256-GCM."""

import base64
import hashlib
import os
from typing import Any, Dict, Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.config import settings


class AESGCMCryptoService:
    """Provides AEAD encryption/decryption for sensitive credentials and tokens."""

    def __init__(self, master_key_source: Optional[Union[str, bytes]] = None):
        raw_key = master_key_source or os.getenv("MASTER_ENCRYPTION_KEY") or settings.secret_key
        if isinstance(raw_key, str):
            # Derive consistent 256-bit key using SHA-256
            self._key = hashlib.sha256(raw_key.encode("utf-8")).digest()
        else:
            self._key = hashlib.sha256(raw_key).digest()
        self._aesgcm = AESGCM(self._key)

    def encrypt_token(self, plaintext: str, associated_data: str = "") -> Dict[str, bytes]:
        """Encrypts plaintext string into AES-256-GCM components: ciphertext, iv, tag, combined."""
        nonce = os.urandom(12)  # 96-bit nonce/IV
        ad_bytes = associated_data.encode("utf-8") if associated_data else None
        # In cryptography.hazmat, AESGCM.encrypt returns ciphertext + 16-byte authentication tag
        ct_with_tag = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), ad_bytes)
        
        ciphertext = ct_with_tag[:-16]
        tag = ct_with_tag[-16:]
        combined = nonce + ct_with_tag  # nonce (12B) + ciphertext + tag (16B)

        return {
            "ciphertext": ciphertext,
            "iv": nonce,
            "tag": tag,
            "combined": combined,
        }

    def decrypt_token(
        self,
        token_data: Any,
        iv: Optional[bytes] = None,
        tag: Optional[bytes] = None,
        associated_data: str = "",
    ) -> str:
        """Decrypts ciphertext using AES-256-GCM.

        Accepts:
        - OAuthCredential instance
        - Combined bytes (nonce + ciphertext + tag)
        - Separated ciphertext, iv and tag
        - Base64 encoded combined string
        """
        ad_bytes = associated_data.encode("utf-8") if associated_data else None

        # 1. Handle OAuthCredential instance
        if hasattr(token_data, "encrypted_access_token"):
            cred = token_data
            if cred.iv_access and cred.tag_access:
                payload = cred.encrypted_access_token + cred.tag_access
                decrypted = self._aesgcm.decrypt(cred.iv_access, payload, ad_bytes)
                return decrypted.decode("utf-8")
            token_data = cred.encrypted_access_token

        # 2. Handle base64 string
        if isinstance(token_data, str):
            token_data = base64.b64decode(token_data.encode("utf-8"))

        # 3. Handle separate IV and Tag
        if iv is not None and tag is not None:
            if isinstance(token_data, (bytes, bytearray)):
                payload = bytes(token_data) + bytes(tag)
                decrypted = self._aesgcm.decrypt(iv, payload, ad_bytes)
                return decrypted.decode("utf-8")

        # 4. Handle combined bytes: nonce (12B) + ciphertext + tag (16B)
        if isinstance(token_data, (bytes, bytearray)):
            raw_bytes = bytes(token_data)
            if len(raw_bytes) < 28:
                raise ValueError("Malformed ciphertext payload: minimum length 28 bytes required.")
            nonce = raw_bytes[:12]
            ct_with_tag = raw_bytes[12:]
            decrypted = self._aesgcm.decrypt(nonce, ct_with_tag, ad_bytes)
            return decrypted.decode("utf-8")

        raise ValueError(f"Unsupported token data type for decryption: {type(token_data)}")


crypto_service = AESGCMCryptoService()


def encrypt_token(plaintext: str, associated_data: str = "") -> Dict[str, bytes]:
    """Convenience helper to encrypt an OAuth token."""
    return crypto_service.encrypt_token(plaintext, associated_data=associated_data)


def decrypt_token(
    token_data: Any,
    iv: Optional[bytes] = None,
    tag: Optional[bytes] = None,
    associated_data: str = "",
) -> str:
    """Convenience helper to decrypt an OAuth token."""
    return crypto_service.decrypt_token(token_data, iv=iv, tag=tag, associated_data=associated_data)
