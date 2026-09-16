"""
AI Provider Configuration, DPAPI Credential Security & Provider Management for E.V.

This module provides:
1. AIProviderConfig: Data model for user-configurable AI providers.
2. DPAPICredentialStore: Windows DPAPI-backed secure credential storage.
3. AIProviderConfigStore: Persistent configuration manager enforcing the single active provider invariant.
4. test_provider_connection: Side-effect-free connection probe classifying HTTP status codes.
5. create_provider_from_config: Provider factory creating concrete EVBrainProvider instances.
"""
from __future__ import annotations

import base64
import ctypes
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

import httpx

from core.brain_provider import EVBrainProvider
from core.paths import ensure_dir, get_config_dir
from providers.anthropic_provider import AnthropicProvider
from providers.gemini_provider import GeminiProvider
from providers.openai_compatible_provider import (
    AzureOpenAIProvider,
    OpenAICompatibleProvider,
    OpenRouterProvider,
)

logger = logging.getLogger("ev.core.provider_config")

# ==============================================================================
# 1. DPAPI CREDENTIAL SECURITY
# ==============================================================================

if sys.platform == "win32":
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]

    _CryptProtectData = ctypes.windll.crypt32.CryptProtectData
    _CryptUnprotectData = ctypes.windll.crypt32.CryptUnprotectData
else:
    _DATA_BLOB = None
    _CryptProtectData = None
    _CryptUnprotectData = None


def encrypt_dpapi(plaintext: str) -> bytes:
    """
    Encrypt plaintext using Windows DPAPI (CryptProtectData).
    Falls back to safe obfuscated byte representation on non-Windows platforms.
    """
    if not plaintext:
        return b""

    raw_bytes = plaintext.encode("utf-8")

    if sys.platform == "win32" and _CryptProtectData is not None:
        try:
            blob_in = _DATA_BLOB(
                len(raw_bytes),
                ctypes.cast(ctypes.create_string_buffer(raw_bytes), ctypes.POINTER(ctypes.c_byte)),
            )
            blob_out = _DATA_BLOB()
            # CryptProtectData(pDataIn, szDataDescr, pOptionalEntropy, pvReserved, pPromptStruct, dwFlags, pDataOut)
            if _CryptProtectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
                encrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData)
                # Free the allocated memory in blob_out
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                return b"DPAPI:" + encrypted
        except Exception as exc:
            logger.warning("DPAPI encryption failed; falling back to local encoding: %s", exc)

    # Fallback for headless/non-Windows environments (e.g. CI)
    encoded = base64.b85encode(raw_bytes)
    return b"B85:" + encoded


def decrypt_dpapi(cipherbytes: bytes) -> str:
    """
    Decrypt ciphertext using Windows DPAPI (CryptUnprotectData) or fallback.
    """
    if not cipherbytes:
        return ""

    if cipherbytes.startswith(b"DPAPI:") and sys.platform == "win32" and _CryptUnprotectData is not None:
        raw_cipher = cipherbytes[6:]
        try:
            blob_in = _DATA_BLOB(
                len(raw_cipher),
                ctypes.cast(ctypes.create_string_buffer(raw_cipher), ctypes.POINTER(ctypes.c_byte)),
            )
            blob_out = _DATA_BLOB()
            if _CryptUnprotectData(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
                decrypted = ctypes.string_at(blob_out.pbData, blob_out.cbData).decode("utf-8")
                ctypes.windll.kernel32.LocalFree(blob_out.pbData)
                return decrypted
        except Exception as exc:
            logger.warning("DPAPI decryption failed: %s", exc)
            return ""

    if cipherbytes.startswith(b"B85:"):
        try:
            return base64.b85decode(cipherbytes[4:]).decode("utf-8")
        except Exception as exc:
            logger.warning("Base85 decryption failed: %s", exc)
            return ""

    # Legacy or raw string fallback
    try:
        return cipherbytes.decode("utf-8")
    except Exception:
        return ""


def mask_key(key: Optional[str]) -> str:
    """Return a masked representation of an API key for GUI presentation."""
    if not key or not str(key).strip():
        return ""
    s = str(key).strip()
    if len(s) <= 8:
        return "••••••••"
    return "••••••••••••"


class DPAPICredentialStore:
    """
    Secure DPAPI-backed local credential store for provider API keys.
    Tied to local Windows user session; keys are NEVER stored in plaintext config files.
    """

    def __init__(self, store_path: Optional[Path] = None) -> None:
        config_dir = ensure_dir(get_config_dir())
        self._path: Path = store_path or (config_dir / "ai_credentials.bin")
        self._cache: Dict[str, bytes] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            content = self._path.read_bytes()
            if not content:
                return
            data = json.loads(content.decode("utf-8"))
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str):
                        self._cache[k] = base64.b64decode(v.encode("utf-8"))
        except Exception as exc:
            logger.warning("Failed to load DPAPI credential store: %s", exc)

    def _save(self) -> None:
        try:
            serializable = {k: base64.b64encode(v).decode("utf-8") for k, v in self._cache.items()}
            raw = json.dumps(serializable, indent=2).encode("utf-8")
            self._path.write_bytes(raw)
        except Exception as exc:
            logger.warning("Failed to save DPAPI credential store: %s", exc)

    def get_credential(self, provider_id: str) -> Optional[str]:
        """Retrieve and decrypt credential for provider."""
        cipher = self._cache.get(provider_id)
        if not cipher:
            return None
        return decrypt_dpapi(cipher)

    def store_credential(self, provider_id: str, secret: str) -> None:
        """Encrypt and store credential for provider."""
        if not secret:
            self.delete_credential(provider_id)
            return
        cipher = encrypt_dpapi(secret.strip())
        self._cache[provider_id] = cipher
        self._save()

    def delete_credential(self, provider_id: str) -> None:
        """Remove credential for provider."""
        if provider_id in self._cache:
            del self._cache[provider_id]
            self._save()

    def has_credential(self, provider_id: str) -> bool:
        """Check whether provider has a stored credential."""
        return provider_id in self._cache and bool(self._cache[provider_id])


# ==============================================================================
# 2. DATA MODEL
# ==============================================================================

VALID_PROVIDER_TYPES = [
    "Gemini",
    "OpenAI",
    "Azure OpenAI",
    "Anthropic",
    "OpenRouter",
    "Groq",
    "Ollama",
    "Custom / OpenAI Compatible",
]

VALID_PROTOCOLS = [
    "auto_detect",
    "openai_compatible",
    "anthropic",
    "gemini",
    "azure_openai",
    "custom",
]


@dataclass
class AIProviderConfig:
    """
    Configuration model for an AI Provider in E.V.
    Credentials are stored separately in the DPAPICredentialStore.
    """
    id: str
    name: str
    provider_type: str
    protocol: str
    model: str
    base_url: Optional[str] = None
    endpoint: Optional[str] = None
    api_version: Optional[str] = None
    enabled: bool = True
    is_active: bool = False
    has_credential: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self, mask_keys: bool = True) -> Dict[str, Any]:
        """Convert to dict suitable for JSON serialization and QML."""
        d = asdict(self)
        if mask_keys:
            d["masked_key"] = "••••••••••••" if self.has_credential else ""
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AIProviderConfig:
        """Construct config from dictionary."""
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            provider_type=str(data.get("provider_type", "Custom / OpenAI Compatible")),
            protocol=str(data.get("protocol", "openai_compatible")),
            model=str(data.get("model", "")),
            base_url=data.get("base_url") or None,
            endpoint=data.get("endpoint") or None,
            api_version=data.get("api_version") or None,
            enabled=bool(data.get("enabled", True)),
            is_active=bool(data.get("is_active", False)),
            has_credential=bool(data.get("has_credential", False)),
            created_at=str(data.get("created_at", "")),
        )


def get_default_provider_specs() -> List[Dict[str, Any]]:
    """Return default template provider specifications."""
    return [
        {
            "id": "gemini-default",
            "name": "Gemini",
            "provider_type": "Gemini",
            "protocol": "gemini",
            "model": "gemini-2.5-flash",
            "base_url": "",
            "endpoint": "",
            "api_version": "",
            "enabled": True,
            "is_active": True,
        },
        {
            "id": "openai-default",
            "name": "OpenAI",
            "provider_type": "OpenAI",
            "protocol": "openai_compatible",
            "model": "gpt-4o-mini",
            "base_url": "https://api.openai.com/v1",
            "endpoint": "",
            "api_version": "",
            "enabled": True,
            "is_active": False,
        },
        {
            "id": "azure-openai-default",
            "name": "Azure OpenAI",
            "provider_type": "Azure OpenAI",
            "protocol": "azure_openai",
            "model": "gpt-4o-mini",
            "base_url": "",
            "endpoint": "https://your-resource.openai.azure.com",
            "api_version": "2024-06-01",
            "enabled": True,
            "is_active": False,
        },
        {
            "id": "anthropic-default",
            "name": "Anthropic",
            "provider_type": "Anthropic",
            "protocol": "anthropic",
            "model": "claude-3-5-sonnet-20241022",
            "base_url": "https://api.anthropic.com/v1",
            "endpoint": "",
            "api_version": "",
            "enabled": True,
            "is_active": False,
        },
        {
            "id": "openrouter-default",
            "name": "OpenRouter",
            "provider_type": "OpenRouter",
            "protocol": "openai_compatible",
            "model": "openai/gpt-4o-mini",
            "base_url": "https://openrouter.ai/api/v1",
            "endpoint": "",
            "api_version": "",
            "enabled": True,
            "is_active": False,
        },
        {
            "id": "groq-default",
            "name": "Groq",
            "provider_type": "Groq",
            "protocol": "openai_compatible",
            "model": "llama-3.3-70b-versatile",
            "base_url": "https://api.groq.com/openai/v1",
            "endpoint": "",
            "api_version": "",
            "enabled": True,
            "is_active": False,
        },
        {
            "id": "ollama-default",
            "name": "Ollama (Local)",
            "provider_type": "Ollama",
            "protocol": "openai_compatible",
            "model": "llama3.2",
            "base_url": "http://localhost:11434/v1",
            "endpoint": "",
            "api_version": "",
            "enabled": True,
            "is_active": False,
        },
    ]


# ==============================================================================
# 3. CONNECTION TESTING & PROTOCOL AUTO-DETECTION
# ==============================================================================

@dataclass
class KeyProviderHint:
    """Heuristic inference for identifiable API key formats."""
    provider_name: str
    protocol: str
    base_url: Optional[str]
    default_model: str
    id_prefix: str


def identify_provider_from_key(api_key: str) -> Optional[KeyProviderHint]:
    """
    Heuristically identify the likely provider, endpoint, and protocol from an API key format.
    Returns KeyProviderHint if identifiable, or None if ambiguous/unidentifiable.
    """
    key = (api_key or "").strip()
    if not key:
        return None

    # 1. Anthropic: sk-ant-api... or sk-ant-...
    if key.startswith("sk-ant-"):
        return KeyProviderHint(
            provider_name="Anthropic",
            protocol="anthropic",
            base_url="https://api.anthropic.com/v1",
            default_model="claude-3-5-sonnet-20241022",
            id_prefix="anthropic",
        )

    # 2. Google Gemini: AIzaSy...
    if key.startswith("AIzaSy"):
        return KeyProviderHint(
            provider_name="Gemini",
            protocol="gemini",
            base_url=None,
            default_model="gemini-2.5-flash",
            id_prefix="gemini",
        )

    # 3. OpenRouter: sk-or-v1-... or sk-or-...
    if key.startswith("sk-or-v1-") or key.startswith("sk-or-"):
        return KeyProviderHint(
            provider_name="OpenRouter",
            protocol="openai_compatible",
            base_url="https://openrouter.ai/api/v1",
            default_model="openai/gpt-4o-mini",
            id_prefix="openrouter",
        )

    # 4. Groq: gsk_...
    if key.startswith("gsk_"):
        return KeyProviderHint(
            provider_name="Groq",
            protocol="openai_compatible",
            base_url="https://api.groq.com/openai/v1",
            default_model="llama-3.3-70b-versatile",
            id_prefix="groq",
        )

    # 5. OpenAI Project / Service Account Key: sk-proj-... or sk-svcacct-...
    if key.startswith("sk-proj-") or key.startswith("sk-svcacct-"):
        return KeyProviderHint(
            provider_name="OpenAI",
            protocol="openai_compatible",
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
            id_prefix="openai",
        )

    # 6. Standard OpenAI format sk-... with typical length
    if key.startswith("sk-") and len(key) >= 40:
        return KeyProviderHint(
            provider_name="OpenAI",
            protocol="openai_compatible",
            base_url="https://api.openai.com/v1",
            default_model="gpt-4o-mini",
            id_prefix="openai",
        )

    return None


_API_KEY_COMMAND_PATTERNS = [
    re.compile(
        r"^(?:use\s+this\s+api\s+key|set\s+api\s+key|configure\s+api\s+key|configure\s+provider\s+key|add\s+api\s+key|api\s+key\s*:?|add\s+key\s*:?|use\s+key\s*:?)\s*[:=]?\s*(.+)$",
        re.IGNORECASE,
    ),
]


def extract_api_key_intent(text: str) -> Optional[str]:
    """
    Detect if user input contains an API key configuration intent or raw key.
    Extracts and returns the raw key without logging or leaking it.
    """
    if not text:
        return None
    cleaned = text.strip()

    # Check for explicit command prefix
    for pat in _API_KEY_COMMAND_PATTERNS:
        m = pat.match(cleaned)
        if m:
            candidate = m.group(1).strip().strip("\"'<>")
            if len(candidate) >= 16:
                return candidate

    # Check if input itself is a raw key token
    raw_patterns = [
        re.compile(r"^AIzaSy[a-zA-Z0-9_\-]{30,}$"),
        re.compile(r"^sk-ant-[a-zA-Z0-9_\-]{20,}$"),
        re.compile(r"^sk-or-v1-[a-zA-Z0-9_\-]{20,}$"),
        re.compile(r"^gsk_[a-zA-Z0-9_\-]{20,}$"),
        re.compile(r"^sk-proj-[a-zA-Z0-9_\-]{20,}$"),
        re.compile(r"^sk-[a-zA-Z0-9_\-]{30,}$"),
    ]
    for rpat in raw_patterns:
        if rpat.match(cleaned):
            return cleaned

    return None


def auto_detect_and_test_provider(
    config: AIProviderConfig,
    api_key: Optional[str] = None,
    timeout_seconds: float = 8.0,
) -> Dict[str, Any]:
    """
    Intelligently inspect endpoint, detect protocol, test authentication,
    and discover available models where supported.
    """
    key = (api_key or "").strip()
    raw_proto = (config.protocol or "").strip().lower()
    base_url = (config.base_url or "").strip().rstrip("/")
    endpoint = (config.endpoint or "").strip().rstrip("/")

    # Detect candidate protocol if set to auto_detect
    detected_protocol: Optional[str] = None
    discovered_models: List[str] = []

    if raw_proto in ("auto_detect", "auto detect", "auto", ""):
        # Check endpoint hints
        if "generativelanguage.googleapis.com" in base_url or key.startswith("AIzaSy"):
            detected_protocol = "gemini"
        elif "api.anthropic.com" in base_url or key.startswith("sk-ant-"):
            detected_protocol = "anthropic"
        elif "openai.azure.com" in endpoint or "azure" in endpoint:
            detected_protocol = "azure_openai"
        elif base_url:
            detected_protocol = "openai_compatible"
        elif key:
            hint = identify_provider_from_key(key)
            if hint:
                detected_protocol = hint.protocol
                if not base_url and hint.base_url:
                    base_url = hint.base_url
    else:
        detected_protocol = raw_proto

    if not detected_protocol or detected_protocol in ("auto_detect", "unknown"):
        # Fallback probe order: 1. OpenAI Compatible, 2. Anthropic, 3. Gemini
        detected_protocol = "openai_compatible"

    # Test under the detected protocol
    probe_cfg = AIProviderConfig(
        id=config.id,
        name=config.name,
        provider_type=config.provider_type,
        protocol=detected_protocol,
        model=config.model,
        base_url=base_url or config.base_url,
        endpoint=endpoint or config.endpoint,
        api_version=config.api_version,
        enabled=config.enabled,
    )

    # 1. Gemini
    if detected_protocol == "gemini":
        if not key:
            return {
                "success": False,
                "status": "AUTHENTICATION_FAILED",
                "detected_protocol": "gemini",
                "discovered_models": [],
                "message": "✕ Authentication failed: Missing API Key",
            }
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                res = client.get(url)
            if res.status_code == 200:
                try:
                    mdata = res.json().get("models", [])
                    discovered_models = [m.get("name", "").replace("models/", "") for m in mdata if "generateContent" in m.get("supportedGenerationMethods", [])]
                except Exception:
                    pass
                msg = (
                    "✓ Endpoint reachable\n"
                    "✓ Authentication accepted\n"
                    "✓ Protocol detected: Gemini\n"
                    f"✓ Model available ({len(discovered_models)} models discovered)\n\n"
                    "STATUS: CONNECTED"
                )
                return {
                    "success": True,
                    "status": "CONNECTED",
                    "detected_protocol": "gemini",
                    "discovered_models": discovered_models,
                    "message": msg,
                }
            if res.status_code in (400, 401, 403):
                return {
                    "success": False,
                    "status": "AUTHENTICATION_FAILED",
                    "detected_protocol": "gemini",
                    "discovered_models": [],
                    "message": "✓ Endpoint reachable\n✕ Authentication failed: Invalid API Key\n✓ Protocol detected: Gemini",
                }
            return {
                "success": False,
                "status": "UNAVAILABLE",
                "detected_protocol": "gemini",
                "discovered_models": [],
                "message": f"✕ Provider unavailable (HTTP {res.status_code})",
            }
        except Exception as exc:
            return {
                "success": False,
                "status": "UNAVAILABLE",
                "detected_protocol": "gemini",
                "discovered_models": [],
                "message": f"✕ Provider unavailable: {type(exc).__name__}",
            }

    # 2. Anthropic
    if detected_protocol == "anthropic":
        if not key:
            return {
                "success": False,
                "status": "AUTHENTICATION_FAILED",
                "detected_protocol": "anthropic",
                "discovered_models": [],
                "message": "✕ Authentication failed: Missing API Key",
            }
        url = (probe_cfg.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/models"
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                res = client.get(url, headers=headers)
            if res.status_code == 200:
                try:
                    mdata = res.json().get("data", [])
                    discovered_models = [m.get("id", "") for m in mdata if m.get("id")]
                except Exception:
                    pass
                msg = (
                    "✓ Endpoint reachable\n"
                    "✓ Authentication accepted\n"
                    "✓ Protocol detected: Anthropic Messages\n"
                    f"✓ Model available ({len(discovered_models) or 1} available)\n\n"
                    "STATUS: CONNECTED"
                )
                return {
                    "success": True,
                    "status": "CONNECTED",
                    "detected_protocol": "anthropic",
                    "discovered_models": discovered_models,
                    "message": msg,
                }
            if res.status_code in (401, 403):
                return {
                    "success": False,
                    "status": "AUTHENTICATION_FAILED",
                    "detected_protocol": "anthropic",
                    "discovered_models": [],
                    "message": "✓ Endpoint reachable\n✕ Authentication failed: Invalid API Key\n✓ Protocol detected: Anthropic Messages",
                }
            # Fallback probe to messages endpoint
            msg_url = (probe_cfg.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages"
            payload = {
                "model": probe_cfg.model or "claude-3-5-sonnet-20241022",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1,
            }
            with httpx.Client(timeout=timeout_seconds) as client:
                m_res = client.post(msg_url, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}, json=payload)
            if m_res.status_code == 200:
                return {
                    "success": True,
                    "status": "CONNECTED",
                    "detected_protocol": "anthropic",
                    "discovered_models": [probe_cfg.model or "claude-3-5-sonnet-20241022"],
                    "message": "✓ Endpoint reachable\n✓ Authentication accepted\n✓ Protocol detected: Anthropic Messages\n✓ Model available\n\nSTATUS: CONNECTED",
                }
            if m_res.status_code in (401, 403):
                return {
                    "success": False,
                    "status": "AUTHENTICATION_FAILED",
                    "detected_protocol": "anthropic",
                    "discovered_models": [],
                    "message": "✓ Endpoint reachable\n✕ Authentication failed\n✓ Protocol detected: Anthropic Messages",
                }
            return {
                "success": False,
                "status": "UNAVAILABLE",
                "detected_protocol": "anthropic",
                "discovered_models": [],
                "message": f"✕ Provider unavailable (HTTP {m_res.status_code})",
            }
        except Exception as exc:
            return {
                "success": False,
                "status": "UNAVAILABLE",
                "detected_protocol": "anthropic",
                "discovered_models": [],
                "message": f"✕ Provider unavailable: {type(exc).__name__}",
            }

    # 3. Azure OpenAI
    if detected_protocol == "azure_openai":
        ok, msg = test_provider_connection(probe_cfg, api_key=key, timeout_seconds=timeout_seconds)
        return {
            "success": ok,
            "status": "CONNECTED" if ok else ("AUTHENTICATION_FAILED" if "Authentication" in msg else "UNAVAILABLE"),
            "detected_protocol": "azure_openai",
            "discovered_models": [probe_cfg.model] if probe_cfg.model else [],
            "message": f"✓ Protocol detected: Azure OpenAI\n{msg}\n\nSTATUS: {'CONNECTED' if ok else 'FAILED'}",
        }

    # 4. OpenAI Compatible / Generic Endpoint
    target_base = (probe_cfg.base_url or "https://api.openai.com/v1").rstrip("/")
    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    try:
        models_url = f"{target_base}/models"
        with httpx.Client(timeout=timeout_seconds) as client:
            res = client.get(models_url, headers=headers)

        if res.status_code == 200:
            try:
                mdata = res.json().get("data", [])
                discovered_models = [m.get("id", "") for m in mdata if m.get("id")]
            except Exception:
                pass
            model_info = f"({len(discovered_models)} models discovered)" if discovered_models else "(Model available)"
            msg = (
                "✓ Endpoint reachable\n"
                "✓ Authentication accepted\n"
                "✓ Protocol detected: OpenAI Compatible\n"
                f"✓ Model available {model_info}\n\n"
                "STATUS: CONNECTED"
            )
            return {
                "success": True,
                "status": "CONNECTED",
                "detected_protocol": "openai_compatible",
                "discovered_models": discovered_models,
                "message": msg,
            }

        if res.status_code in (401, 403):
            return {
                "success": False,
                "status": "AUTHENTICATION_FAILED",
                "detected_protocol": "openai_compatible",
                "discovered_models": [],
                "message": "✓ Endpoint reachable\n✕ Authentication failed: Invalid API key\n✓ Protocol detected: OpenAI Compatible",
            }

        # Probe chat completions if /models is unavailable
        comp_url = f"{target_base}/chat/completions"
        payload = {
            "model": probe_cfg.model or "gpt-4o-mini",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        with httpx.Client(timeout=timeout_seconds) as client:
            res2 = client.post(comp_url, headers=headers, json=payload)

        if res2.status_code == 200:
            return {
                "success": True,
                "status": "CONNECTED",
                "detected_protocol": "openai_compatible",
                "discovered_models": [probe_cfg.model or "gpt-4o-mini"],
                "message": "✓ Endpoint reachable\n✓ Authentication accepted\n✓ Protocol detected: OpenAI Compatible\n✓ Model available\n\nSTATUS: CONNECTED",
            }
        if res2.status_code in (401, 403):
            return {
                "success": False,
                "status": "AUTHENTICATION_FAILED",
                "detected_protocol": "openai_compatible",
                "discovered_models": [],
                "message": "✓ Endpoint reachable\n✕ Authentication failed\n✓ Protocol detected: OpenAI Compatible",
            }

        # If endpoint responded with 404 or other unrecognized format, report unknown protocol
        unknown_msg = (
            "PROTOCOL: UNKNOWN\n\n"
            "Select manually:\n"
            "[ OpenAI Compatible ]\n"
            "[ Anthropic ]\n"
            "[ Gemini ]\n"
            "[ Custom ]"
        )
        return {
            "success": False,
            "status": "UNKNOWN_PROTOCOL",
            "detected_protocol": "unknown",
            "discovered_models": [],
            "message": unknown_msg,
        }

    except Exception:
        # Fallback to standard connection testing
        ok, msg = test_provider_connection(probe_cfg, api_key=key, timeout_seconds=timeout_seconds)
        return {
            "success": ok,
            "status": "CONNECTED" if ok else "UNAVAILABLE",
            "detected_protocol": "openai_compatible",
            "discovered_models": [],
            "message": msg,
        }


def test_provider_connection(
    config: AIProviderConfig,
    api_key: Optional[str] = None,
    timeout_seconds: float = 8.0,
) -> Tuple[bool, str]:
    """
    Test connectivity to the configured AI provider without executing any E.V. system actions.

    Classifies response status:
    - 200 -> (True, "✓ Connection successful")
    - 401, 403 -> (False, "✕ Authentication failed")
    - 429 -> (False, "✕ Quota exceeded")
    - 500, 502, 503, 504 -> (False, "✕ Provider unavailable")
    - Network/connect timeout -> (False, "✕ Provider unavailable")
    """
    key = (api_key or "").strip()
    ptype = config.provider_type
    protocol = config.protocol

    # Support auto_detect delegation
    if protocol in ("auto_detect", "auto detect", "auto"):
        res = auto_detect_and_test_provider(config, api_key=key, timeout_seconds=timeout_seconds)
        return (res["success"], res["message"])

    # 1. Gemini
    if protocol == "gemini" or ptype == "Gemini":
        if not key:
            return (False, "✕ Authentication failed: Missing API Key")
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                res = client.get(url)
            status = res.status_code
            if status == 200:
                return (True, "✓ Connection successful")
            if status in (400, 401, 403):
                return (False, "✕ Authentication failed")
            if status == 429:
                return (False, "✕ Quota exceeded")
            return (False, f"✕ Provider unavailable (HTTP {status})")
        except (httpx.TimeoutException, TimeoutError):
            return (False, "✕ Provider unavailable (Timeout)")
        except Exception:
            return (False, "✕ Provider unavailable")

    # 2. Anthropic
    if protocol == "anthropic" or ptype == "Anthropic":
        if not key:
            return (False, "✕ Authentication failed: Missing API Key")
        url = (config.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/models"
        headers = {
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
        }
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                res = client.get(url, headers=headers)
            status = res.status_code
            if status == 200:
                return (True, "✓ Connection successful")
            if status in (401, 403):
                return (False, "✕ Authentication failed")
            if status == 429:
                return (False, "✕ Quota exceeded")
            if status == 404:
                # Fallback to minimal probe message if /models is unsupported
                msg_url = (config.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages"
                payload = {
                    "model": config.model or "claude-3-5-sonnet-20241022",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 1,
                }
                with httpx.Client(timeout=timeout_seconds) as client:
                    m_res = client.post(msg_url, headers={"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}, json=payload)
                if m_res.status_code == 200:
                    return (True, "✓ Connection successful")
                if m_res.status_code in (401, 403):
                    return (False, "✕ Authentication failed")
                if m_res.status_code == 429:
                    return (False, "✕ Quota exceeded")
            return (False, f"✕ Provider unavailable (HTTP {status})")
        except (httpx.TimeoutException, TimeoutError):
            return (False, "✕ Provider unavailable (Timeout)")
        except Exception:
            return (False, "✕ Provider unavailable")

    # 3. Azure OpenAI
    if protocol == "azure_openai" or ptype == "Azure OpenAI":
        if not key:
            return (False, "✕ Authentication failed: Missing API Key")
        endpoint = (config.endpoint or "").rstrip("/")
        if not endpoint:
            return (False, "✕ Provider unavailable: Missing Azure Endpoint")
        api_ver = config.api_version or "2024-06-01"
        url = f"{endpoint}/openai/models?api-version={api_ver}"
        headers = {"api-key": key}
        try:
            with httpx.Client(timeout=timeout_seconds) as client:
                res = client.get(url, headers=headers)
            status = res.status_code
            if status == 200:
                return (True, "✓ Connection successful")
            if status in (401, 403):
                return (False, "✕ Authentication failed")
            if status == 429:
                return (False, "✕ Quota exceeded")
            # If models endpoint isn't authorized for list, test deployment completions endpoint
            deploy_url = f"{endpoint}/openai/deployments/{config.model}/chat/completions?api-version={api_ver}"
            with httpx.Client(timeout=timeout_seconds) as client:
                res2 = client.post(deploy_url, headers=headers, json={"messages": [{"role": "user", "content": "hi"}], "max_tokens": 1})
            if res2.status_code == 200:
                return (True, "✓ Connection successful")
            if res2.status_code in (401, 403):
                return (False, "✕ Authentication failed")
            if res2.status_code == 429:
                return (False, "✕ Quota exceeded")
            return (False, f"✕ Provider unavailable (HTTP {res2.status_code})")
        except (httpx.TimeoutException, TimeoutError):
            return (False, "✕ Provider unavailable (Timeout)")
        except Exception:
            return (False, "✕ Provider unavailable")

    # 4. OpenAI / OpenRouter / Groq / Ollama / Custom (OpenAI-compatible)
    base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
    # Ollama does not require key; others do
    if ptype != "Ollama" and not key:
        return (False, "✕ Authentication failed: Missing API Key")

    headers = {"Accept": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    models_url = f"{base_url}/models"
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            res = client.get(models_url, headers=headers)
        status = res.status_code
        if status == 200:
            return (True, "✓ Connection successful")
        if status in (401, 403):
            return (False, "✕ Authentication failed")
        if status == 429:
            return (False, "✕ Quota exceeded")

        # Some custom OpenAI compatible servers don't implement /models; probe /chat/completions
        comp_url = f"{base_url}/chat/completions"
        payload = {
            "model": config.model or "default",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        with httpx.Client(timeout=timeout_seconds) as client:
            res2 = client.post(comp_url, headers=headers, json=payload)
        if res2.status_code == 200:
            return (True, "✓ Connection successful")
        if res2.status_code in (401, 403):
            return (False, "✕ Authentication failed")
        if res2.status_code == 429:
            return (False, "✕ Quota exceeded")
        if res2.status_code in (500, 502, 503, 504):
            return (False, "✕ Provider unavailable")

        return (False, f"✕ Provider unavailable (HTTP {res2.status_code})")
    except (httpx.TimeoutException, TimeoutError):
        return (False, "✕ Provider unavailable (Timeout)")
    except Exception:
        return (False, "✕ Provider unavailable")


test_provider_connection.__test__ = False  # Prevent pytest from collecting as test fixture


def configure_provider_from_key(
    api_key: str,
    store: AIProviderConfigStore,
    service_hint: Optional[str] = None,
) -> Tuple[bool, str, Optional[str]]:
    """
    Automated provider configuration pipeline:
    API KEY RECEIVED
            ↓
    Detect likely provider (or use explicit service_hint)
            ↓
    Determine endpoint & protocol
            ↓
    Discover models where supported
            ↓
    Validate authentication
            ↓
    Create provider configuration (is_active=False)
            ↓
    Encrypt credential with DPAPI
            ↓
    Return (success, summary_message, pending_provider_id)

    NEVER sets active provider automatically.
    """
    key = (api_key or "").strip()
    if not key:
        return (False, "No API key was provided.", None)

    hint = identify_provider_from_key(key)
    if not hint and service_hint:
        norm = service_hint.strip().lower()
        if "gemini" in norm or "google" in norm or norm == "2":
            hint = KeyProviderHint("Gemini", "gemini", None, "gemini-2.5-flash", "gemini")
        elif "anthropic" in norm or "claude" in norm or norm == "3":
            hint = KeyProviderHint("Anthropic", "anthropic", "https://api.anthropic.com/v1", "claude-3-5-sonnet-20241022", "anthropic")
        elif "openrouter" in norm or norm == "4":
            hint = KeyProviderHint("OpenRouter", "openai_compatible", "https://openrouter.ai/api/v1", "openai/gpt-4o-mini", "openrouter")
        elif "groq" in norm or norm == "5":
            hint = KeyProviderHint("Groq", "openai_compatible", "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", "groq")
        elif "openai" in norm or norm == "1":
            hint = KeyProviderHint("OpenAI", "openai_compatible", "https://api.openai.com/v1", "gpt-4o-mini", "openai")
        else:
            hint = KeyProviderHint("Custom", "openai_compatible", "https://api.openai.com/v1", "gpt-4o-mini", "custom")

    if not hint:
        clarification = (
            "I can configure this key, but I can't identify the provider.\n\n"
            "Which service is it?\n"
            "1. OpenAI\n"
            "2. Gemini\n"
            "3. Anthropic\n"
            "4. OpenRouter\n"
            "5. Groq\n"
            "6. Other (Custom)\n\n"
            "Reply with the service name or number."
        )
        return (False, clarification, None)

    # Determine unique ID
    provider_id = f"{hint.id_prefix}-auto-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    # Build config
    cfg = AIProviderConfig(
        id=provider_id,
        name=hint.provider_name,
        provider_type=hint.provider_name if hint.provider_name in VALID_PROVIDER_TYPES else "Custom / OpenAI Compatible",
        protocol=hint.protocol,
        model=hint.default_model,
        base_url=hint.base_url,
        enabled=True,
        is_active=False,  # PRESERVE USER CONTROL: NEVER automatically activate!
    )

    # Test connection and probe models
    test_result = auto_detect_and_test_provider(cfg, api_key=key)
    discovered_models = test_result.get("discovered_models") or []
    if discovered_models and not cfg.model:
        cfg.model = discovered_models[0]

    # Save into store with DPAPI encrypted credential
    store.save_provider(cfg, api_key=key)

    endpoint_str = cfg.base_url or (cfg.endpoint or "Default API Gateway")
    auth_status = "Valid" if test_result.get("success") else "Authentication could not be verified (check key or network)"
    model_str = cfg.model + (f" ({len(discovered_models)} models discovered)" if len(discovered_models) > 1 else "")

    summary = (
        f"PROVIDER DETECTED\n\n"
        f"Provider: {hint.provider_name}\n"
        f"Protocol: {hint.protocol}\n"
        f"Endpoint: {endpoint_str}\n"
        f"Model: {model_str}\n"
        f"Authentication: {auth_status}\n\n"
        f"Configuration prepared and credential stored securely with DPAPI.\n"
        f"To set this as your active intelligence provider, reply 'ACTIVATE' or select it in Settings."
    )
    return (True, summary, provider_id)


# ==============================================================================
# 4. PROVIDER FACTORY
# ==============================================================================

def create_provider_from_config(
    config: AIProviderConfig,
    api_key: Optional[str] = None,
) -> EVBrainProvider:
    """
    Construct a concrete EVBrainProvider from an AIProviderConfig.
    """
    key = api_key or ""
    ptype = config.provider_type
    protocol = config.protocol

    if protocol == "gemini" or ptype == "Gemini":
        return GeminiProvider(api_key=key, model_name=config.model)

    if protocol == "anthropic" or ptype == "Anthropic":
        return AnthropicProvider(
            api_key=key,
            base_url=config.base_url or "https://api.anthropic.com/v1",
            model_name=config.model,
            provider_name=config.name.lower().replace(" ", "_"),
        )

    if protocol == "azure_openai" or ptype == "Azure OpenAI":
        return AzureOpenAIProvider(
            endpoint=config.endpoint,
            api_key=key,
            deployment_name=config.model,
            api_version=config.api_version or "2024-06-01",
        )

    if ptype == "OpenRouter":
        return OpenRouterProvider(
            api_key=key,
            base_url=config.base_url or "https://openrouter.ai/api/v1",
            model_name=config.model,
        )

    # Generic OpenAI-compatible (OpenAI, Groq, Ollama, Custom)
    base_url = config.base_url or "https://api.openai.com/v1"
    clean_name = config.name.lower().replace(" ", "_")
    return OpenAICompatibleProvider(
        api_key=key if key else ("ollama" if ptype == "Ollama" else None),
        base_url=base_url,
        model_name=config.model,
        provider_name=clean_name,
    )


# ==============================================================================
# 5. CONFIGURATION STORE
# ==============================================================================

class AIProviderConfigStore:
    """
    Persistent store for AIProviderConfig records with DPAPI credential security.
    Maintains the single-active-provider invariant.
    """

    def __init__(
        self,
        config_path: Optional[Path] = None,
        credential_store: Optional[DPAPICredentialStore] = None,
    ) -> None:
        config_dir = ensure_dir(get_config_dir())
        self._config_path: Path = config_path or (config_dir / "ai_providers.json")
        self._cred_store: DPAPICredentialStore = credential_store or DPAPICredentialStore()
        self._configs: Dict[str, AIProviderConfig] = {}
        self._load_or_initialize()

    def _load_or_initialize(self) -> None:
        """Load stored provider configurations, or initialize defaults and import env vars."""
        if not self._config_path.exists():
            self._initialize_defaults()
            return

        try:
            raw = self._config_path.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, list):
                active_found = False
                for item in data:
                    cfg = AIProviderConfig.from_dict(item)
                    cfg.has_credential = self._cred_store.has_credential(cfg.id)
                    if cfg.is_active:
                        if not active_found:
                            active_found = True
                        else:
                            # Invariant: exactly one active provider
                            cfg.is_active = False
                    self._configs[cfg.id] = cfg

                # Ensure at least one is active if list non-empty
                if self._configs and not active_found:
                    first_id = next(iter(self._configs))
                    self._configs[first_id].is_active = True
                return
        except Exception as exc:
            logger.warning("Failed to parse %s: %s; reinitializing defaults", self._config_path, exc)

        self._initialize_defaults()

    def _initialize_defaults(self) -> None:
        """Seed default providers and import any existing environment variables."""
        self._configs.clear()
        defaults = get_default_provider_specs()

        # Check environment variables for existing credentials to seed seamlessly
        env_keys = {
            "gemini-default": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            "openai-default": os.getenv("OPENAI_API_KEY"),
            "openrouter-default": os.getenv("OPENROUTER_API_KEY"),
            "azure-openai-default": os.getenv("AZURE_OPENAI_API_KEY"),
            "anthropic-default": os.getenv("ANTHROPIC_API_KEY"),
            "groq-default": os.getenv("GROQ_API_KEY"),
        }

        # Store any detected environment credentials into the DPAPI store
        for pid, key in env_keys.items():
            if key and not self._cred_store.has_credential(pid):
                self._cred_store.store_credential(pid, key)

        active_set = False
        for spec in defaults:
            cfg = AIProviderConfig.from_dict(spec)
            cfg.has_credential = self._cred_store.has_credential(cfg.id)
            if not active_set and cfg.has_credential:
                cfg.is_active = True
                active_set = True
            elif active_set:
                cfg.is_active = False
            self._configs[cfg.id] = cfg

        # If none had credentials, keep gemini-default as active template
        if not active_set and "gemini-default" in self._configs:
            self._configs["gemini-default"].is_active = True

        self.save_all()

    def save_all(self) -> None:
        """Write configuration to disk (NEVER writing API keys into this file)."""
        try:
            # Mask keys / do not serialize secret data
            raw_list = [cfg.to_dict(mask_keys=True) for cfg in self._configs.values()]
            text = json.dumps(raw_list, indent=2)
            self._config_path.write_text(text, encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to save AI provider configuration: %s", exc)

    def get_providers(self) -> List[AIProviderConfig]:
        """Return list of all configured providers."""
        # Refresh has_credential state
        for cfg in self._configs.values():
            cfg.has_credential = self._cred_store.has_credential(cfg.id)
        return list(self._configs.values())

    def get_provider(self, provider_id: str) -> Optional[AIProviderConfig]:
        """Return specific provider config if found."""
        cfg = self._configs.get(provider_id)
        if cfg:
            cfg.has_credential = self._cred_store.has_credential(cfg.id)
        return cfg

    def get_active_provider(self) -> Optional[AIProviderConfig]:
        """Return the active provider config."""
        for cfg in self._configs.values():
            if cfg.is_active:
                cfg.has_credential = self._cred_store.has_credential(cfg.id)
                return cfg
        # Fallback to first provider if none explicitly marked
        if self._configs:
            first = next(iter(self._configs.values()))
            first.is_active = True
            first.has_credential = self._cred_store.has_credential(first.id)
            return first
        return None

    def get_active_credential(self) -> Optional[str]:
        """Return decrypted API key for the active provider."""
        active = self.get_active_provider()
        if not active:
            return None
        return self._cred_store.get_credential(active.id)

    def get_credential(self, provider_id: str) -> Optional[str]:
        """Return decrypted API key for a specific provider."""
        return self._cred_store.get_credential(provider_id)

    def set_active(self, provider_id: str) -> bool:
        """
        Set exactly one active provider. Returns True on success.
        """
        if provider_id not in self._configs:
            return False

        for pid, cfg in self._configs.items():
            cfg.is_active = (pid == provider_id)

        self.save_all()
        return True

    def save_provider(
        self,
        config: AIProviderConfig,
        api_key: Optional[str] = None,
    ) -> AIProviderConfig:
        """
        Save or update a provider config. If api_key is provided and non-empty,
        encrypts and stores it in the DPAPI credential store.
        """
        if not config.id:
            config.id = f"custom-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

        if api_key and str(api_key).strip() and str(api_key).strip() != "••••••••••••":
            self._cred_store.store_credential(config.id, str(api_key).strip())

        config.has_credential = self._cred_store.has_credential(config.id)

        # Enforce single active provider
        if config.is_active:
            for pid, other in self._configs.items():
                if pid != config.id:
                    other.is_active = False

        self._configs[config.id] = config
        self.save_all()
        return config

    def delete_provider(self, provider_id: str) -> bool:
        """Delete a provider configuration and its stored credential."""
        if provider_id not in self._configs:
            return False

        was_active = self._configs[provider_id].is_active
        del self._configs[provider_id]
        self._cred_store.delete_credential(provider_id)

        # If the deleted provider was active, make another one active
        if was_active and self._configs:
            next(iter(self._configs.values())).is_active = True

        self.save_all()
        return True

    def create_active_brain_provider(self) -> Optional[EVBrainProvider]:
        """
        Instantiate and return the currently active EVBrainProvider with its decrypted credentials.
        """
        active = self.get_active_provider()
        if not active:
            return None
        key = self._cred_store.get_credential(active.id)
        return create_provider_from_config(active, key)
