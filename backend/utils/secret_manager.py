"""
KayaPure Commerce OS - Secret Manager
Manages API keys securely. Keys are only decrypted and passed to Guest VMs
at the moment of execution, never stored in plaintext in the VM image.
"""

import hashlib
import base64
import json
from cryptography.fernet import Fernet
from typing import Dict, Optional
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings


class SecretManager:
    """
    Manages encrypted secrets for the KayaPure Commerce OS.
    In production, this would integrate with AWS Secrets Manager or HashiCorp Vault.
    """

    def __init__(self):
        # Derive a Fernet key from the encryption key
        key_bytes = settings.ENCRYPTION_KEY.encode()[:32].ljust(32, b'\0')
        self._fernet = Fernet(base64.urlsafe_b64encode(key_bytes))
        self._secrets: Dict[str, str] = {}
        self._load_secrets()

    def _load_secrets(self):
        """Load secrets from environment variables."""
        self._secrets = {
            "shopify_api_key": settings.SHOPIFY_API_KEY,
            "meta_ads_api_key": settings.META_ADS_API_KEY,
            "amazon_sp_api_key": settings.AMAZON_SP_API_KEY,
            "flexport_api_key": settings.FLEXPORT_API_KEY,
            "openai_api_key": settings.OPENAI_API_KEY,
        }

    def get_secret(self, key: str) -> Optional[str]:
        """Retrieve a secret by key name."""
        return self._secrets.get(key)

    def encrypt_payload(self, payload: dict) -> bytes:
        """Encrypt a payload for transmission to a Guest VM via Vsock."""
        json_bytes = json.dumps(payload).encode()
        return self._fernet.encrypt(json_bytes)

    def decrypt_payload(self, encrypted: bytes) -> dict:
        """Decrypt a payload received from the Host."""
        decrypted = self._fernet.decrypt(encrypted)
        return json.loads(decrypted.decode())

    def create_vm_payload(self, action_type: str, parameters: dict) -> dict:
        """
        Create a secure payload for VM execution.
        Injects only the required API keys for the specific action.
        """
        required_keys = self._get_required_keys(action_type)
        secrets = {k: self._secrets[k] for k in required_keys if k in self._secrets}

        payload = {
            "action_type": action_type,
            "parameters": parameters,
            "secrets": secrets,
        }
        return payload

    def _get_required_keys(self, action_type: str) -> list:
        """Determine which API keys are needed for a given action type."""
        key_map = {
            "price_change": ["shopify_api_key"],
            "budget_reduction": ["meta_ads_api_key"],
            "inventory_check": ["flexport_api_key"],
            "competitor_analysis": ["amazon_sp_api_key"],
            "bundle_offer": ["shopify_api_key"],
            "ad_bid_adjustment": ["meta_ads_api_key"],
        }
        return key_map.get(action_type, [])

    def hash_payload(self, payload: dict) -> str:
        """Generate SHA-256 hash of a payload for audit trail."""
        json_bytes = json.dumps(payload, sort_keys=True).encode()
        return hashlib.sha256(json_bytes).hexdigest()


# Singleton instance
secret_manager = SecretManager()
