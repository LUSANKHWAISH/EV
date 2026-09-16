"""
Unit tests for AI Provider Configuration, DPAPI Security & Connection Testing (Task 018-K.3).
"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from core.provider_config import (
    AIProviderConfig,
    AIProviderConfigStore,
    DPAPICredentialStore,
    create_provider_from_config,
    decrypt_dpapi,
    encrypt_dpapi,
    mask_key,
    test_provider_connection as check_provider_connection,
)


@pytest.fixture
def temp_config_dir(tmp_path: Path):
    """Temporary isolated directory for config store testing."""
    return tmp_path


def test_dpapi_encryption_decryption_roundtrip():
    """Verify that DPAPI encryption and decryption recover the exact original secret."""
    secret = "sk-test-secret-key-12345-long-random"
    encrypted = encrypt_dpapi(secret)
    assert encrypted != secret.encode("utf-8")
    assert len(encrypted) > 0

    decrypted = decrypt_dpapi(encrypted)
    assert decrypted == secret


def test_dpapi_empty_string_handling():
    """Empty strings should encrypt and decrypt gracefully."""
    assert encrypt_dpapi("") == b""
    assert decrypt_dpapi(b"") == ""


def test_mask_key():
    """Verify API keys are masked for UI presentation."""
    assert mask_key("") == ""
    assert mask_key("short") == "••••••••"
    assert mask_key("sk-long-secret-key-123456789") == "••••••••••••"


def test_credential_store_isolation(temp_config_dir: Path):
    """Verify credential store stores, retrieves, and deletes encrypted keys."""
    cred_file = temp_config_dir / "test_creds.bin"
    store = DPAPICredentialStore(store_path=cred_file)

    store.store_credential("gemini-test", "gemini-api-key-999")
    assert store.has_credential("gemini-test")
    assert store.get_credential("gemini-test") == "gemini-api-key-999"

    # Verify plaintext is not stored in the file
    raw_content = cred_file.read_bytes()
    assert b"gemini-api-key-999" not in raw_content

    # Reload fresh instance from disk
    store2 = DPAPICredentialStore(store_path=cred_file)
    assert store2.get_credential("gemini-test") == "gemini-api-key-999"

    # Delete
    store2.delete_credential("gemini-test")
    assert not store2.has_credential("gemini-test")
    assert store2.get_credential("gemini-test") is None


def test_config_store_initialization_and_single_active_invariant(temp_config_dir: Path):
    """Verify store initializes defaults and maintains exactly one active provider."""
    conf_path = temp_config_dir / "ai_providers.json"
    cred_path = temp_config_dir / "creds.bin"
    cred_store = DPAPICredentialStore(store_path=cred_path)

    store = AIProviderConfigStore(config_path=conf_path, credential_store=cred_store)
    providers = store.get_providers()
    assert len(providers) >= 5

    # Check that exactly one provider is active
    active_providers = [p for p in providers if p.is_active]
    assert len(active_providers) == 1

    # Switch active provider
    second_id = providers[1].id
    store.set_active(second_id)

    active_after = [p for p in store.get_providers() if p.is_active]
    assert len(active_after) == 1
    assert active_after[0].id == second_id


def test_custom_openai_compatible_provider(temp_config_dir: Path):
    """Verify a custom OpenAI-compatible provider can be created, persisted, and instantiated."""
    conf_path = temp_config_dir / "ai_providers.json"
    cred_path = temp_config_dir / "creds.bin"
    cred_store = DPAPICredentialStore(store_path=cred_path)
    store = AIProviderConfigStore(config_path=conf_path, credential_store=cred_store)

    custom_cfg = AIProviderConfig(
        id="custom-vllm",
        name="Local VLLM",
        provider_type="Custom / OpenAI Compatible",
        protocol="openai_compatible",
        model="deepseek-r1",
        base_url="http://192.168.1.50:8000/v1",
        enabled=True,
        is_active=False,
    )
    store.save_provider(custom_cfg, api_key="vllm-secret-key")

    # Verify retrieval
    retrieved = store.get_provider("custom-vllm")
    assert retrieved is not None
    assert retrieved.name == "Local VLLM"
    assert retrieved.base_url == "http://192.168.1.50:8000/v1"
    assert retrieved.has_credential is True
    assert store.get_credential("custom-vllm") == "vllm-secret-key"

    # Verify serialized JSON never contains plaintext key
    json_text = conf_path.read_text(encoding="utf-8")
    assert "vllm-secret-key" not in json_text

    # Verify provider factory instantiates it as OpenAICompatibleProvider
    provider_inst = create_provider_from_config(retrieved, api_key=store.get_credential("custom-vllm"))
    assert provider_inst.provider_name == "local_vllm"
    assert provider_inst.model_name == "deepseek-r1"
    assert getattr(provider_inst, "base_url", None) == "http://192.168.1.50:8000/v1"


def test_connection_test_success_and_failures():
    """Verify test_provider_connection correctly classifies HTTP status codes."""
    cfg = AIProviderConfig(
        id="test-p",
        name="Test Provider",
        provider_type="OpenAI",
        protocol="openai_compatible",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
    )

    # 1. Success (200)
    mock_resp_200 = MagicMock()
    mock_resp_200.status_code = 200
    with patch("httpx.Client.get", return_value=mock_resp_200):
        ok, msg = check_provider_connection(cfg, api_key="sk-valid-key")
        assert ok is True
        assert "✓ Connection successful" in msg

    # 2. Auth Failure (401)
    mock_resp_401 = MagicMock()
    mock_resp_401.status_code = 401
    with patch("httpx.Client.get", return_value=mock_resp_401):
        ok, msg = check_provider_connection(cfg, api_key="sk-invalid-key")
        assert ok is False
        assert "✕ Authentication failed" in msg

    # 3. Quota Exceeded (429)
    mock_resp_429 = MagicMock()
    mock_resp_429.status_code = 429
    with patch("httpx.Client.get", return_value=mock_resp_429):
        ok, msg = check_provider_connection(cfg, api_key="sk-rate-limited")
        assert ok is False
        assert "✕ Quota exceeded" in msg

    # 4. Unavailable (503)
    mock_resp_503 = MagicMock()
    mock_resp_503.status_code = 503
    with patch("httpx.Client.get", return_value=mock_resp_503):
        with patch("httpx.Client.post", return_value=mock_resp_503):
            ok, msg = check_provider_connection(cfg, api_key="sk-down")
            assert ok is False
            assert "✕ Provider unavailable" in msg

    # 5. Network / ConnectError
    with patch("httpx.Client.get", side_effect=httpx.ConnectError("Network is unreachable")):
        ok, msg = check_provider_connection(cfg, api_key="sk-network-down")
        assert ok is False
        assert "✕ Provider unavailable" in msg


def test_gemini_connection_test():
    """Verify Gemini connection test behaves correctly."""
    cfg = AIProviderConfig(
        id="gemini-test",
        name="Gemini",
        provider_type="Gemini",
        protocol="gemini",
        model="gemini-2.5-flash",
    )

    # Missing key
    ok, msg = check_provider_connection(cfg, api_key="")
    assert ok is False
    assert "Authentication failed" in msg

    # Valid key (200)
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("httpx.Client.get", return_value=mock_resp):
        ok, msg = check_provider_connection(cfg, api_key="AIzaSyValidKey")
        assert ok is True
        assert "✓ Connection successful" in msg


def test_extract_api_key_intent():
    """Verify that extract_api_key_intent extracts keys from natural commands or raw tokens."""
    from core.provider_config import extract_api_key_intent

    # Commands with prefixes
    assert extract_api_key_intent("Use this API key: AIzaSyDUMMY_XXXXXXXXXXXXXXXXXXXXXXXXXX") == "AIzaSyDUMMY_XXXXXXXXXXXXXXXXXXXXXXXXXX"
    assert extract_api_key_intent("set api key: sk-ant-api03-12345678901234567890") == "sk-ant-api03-12345678901234567890"
    assert extract_api_key_intent("configure provider key sk-or-v1-abcdef0123456789abcdef0123456789") == "sk-or-v1-abcdef0123456789abcdef0123456789"

    # Raw tokens
    assert extract_api_key_intent("AIzaSyDUMMY_XXXXXXXXXXXXXXXXXXXXXXXXXX") == "AIzaSyDUMMY_XXXXXXXXXXXXXXXXXXXXXXXXXX"
    assert extract_api_key_intent("sk-ant-api03-12345678901234567890") == "sk-ant-api03-12345678901234567890"

    # Normal user messages should NOT match
    assert extract_api_key_intent("hello there") is None
    assert extract_api_key_intent("list files in current directory") is None


def test_identify_provider_from_key():
    """Verify provider identification from key prefixes and unknown handling."""
    from core.provider_config import identify_provider_from_key

    # Identifiable keys
    h1 = identify_provider_from_key("AIzaSyTest1234567890123456789012345")
    assert h1 is not None and h1.provider_name == "Gemini"

    h2 = identify_provider_from_key("sk-ant-api03-testkey1234567890")
    assert h2 is not None and h2.provider_name == "Anthropic"

    h3 = identify_provider_from_key("sk-or-v1-testkey1234567890")
    assert h3 is not None and h3.provider_name == "OpenRouter"

    h4 = identify_provider_from_key("gsk_testkey1234567890")
    assert h4 is not None and h4.provider_name == "Groq"

    # Unidentifiable key (e.g. generic bearer or custom hex token)
    h_unknown = identify_provider_from_key("custom-internal-key-999888777666")
    assert h_unknown is None, "Unknown key format must return None to prevent dangerous guessing"


def test_auto_detect_and_test_provider():
    """Verify auto_detect_and_test_provider probes endpoint and discovers models."""
    from core.provider_config import auto_detect_and_test_provider

    cfg = AIProviderConfig(
        id="custom-auto",
        name="Custom OpenAI",
        provider_type="Custom / OpenAI Compatible",
        protocol="auto_detect",
        model="gpt-4o-mini",
        base_url="https://api.openai.com/v1",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": [{"id": "gpt-4o-mini"}, {"id": "gpt-4o"}]
    }

    with patch("httpx.Client.get", return_value=mock_resp):
        res = auto_detect_and_test_provider(cfg, api_key="sk-test-key-1234")
        assert res["success"] is True
        assert res["status"] == "CONNECTED"
        assert res["detected_protocol"] == "openai_compatible"
        assert "gpt-4o-mini" in res["discovered_models"]


def test_configure_provider_from_key_known_and_activation_safety(temp_config_dir: Path):
    """Verify configure_provider_from_key prepares config with is_active=False and requires explicit activation."""
    from core.provider_config import configure_provider_from_key

    conf_path = temp_config_dir / "ai_providers.json"
    cred_path = temp_config_dir / "creds.bin"
    store = AIProviderConfigStore(config_path=conf_path, credential_store=DPAPICredentialStore(cred_path))

    # Existing active provider
    init_active = store.get_active_provider()
    assert init_active is not None

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"models": [{"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]}]}

    with patch("httpx.Client.get", return_value=mock_resp):
        ok, summary, p_id = configure_provider_from_key("AIzaSyTest1234567890123456789012345", store)
        assert ok is True
        assert p_id is not None
        assert "PROVIDER DETECTED" in summary
        assert "Gemini" in summary

        # CRITICAL INVARIANT: Receiving key must NOT automatically activate provider!
        current_active = store.get_active_provider()
        assert current_active.id == init_active.id, "Auto-setup must preserve user control (is_active=False)"

        # Verify new provider was saved with credential
        new_provider = store.get_provider(p_id)
        assert new_provider is not None
        assert new_provider.has_credential is True
        assert store.get_credential(p_id) == "AIzaSyTest1234567890123456789012345"

        # Explicit activation by user
        activated = store.set_active(p_id)
        assert activated is True
        assert store.get_active_provider().id == p_id


def test_configure_provider_from_key_unknown_clarification(temp_config_dir: Path):
    """Verify unknown key triggers a clear clarification prompt without guessing."""
    from core.provider_config import configure_provider_from_key

    conf_path = temp_config_dir / "ai_providers.json"
    cred_path = temp_config_dir / "creds.bin"
    store = AIProviderConfigStore(config_path=conf_path, credential_store=DPAPICredentialStore(cred_path))

    ok, msg, p_id = configure_provider_from_key("unidentified-key-12345678901234567890", store)
    assert ok is False
    assert p_id is None
    assert "I can configure this key, but I can't identify the provider." in msg
    assert "Which service is it?" in msg

