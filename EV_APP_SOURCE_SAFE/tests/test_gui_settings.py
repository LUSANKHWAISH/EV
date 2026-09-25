"""
Tests for E.V. Settings Interface & AI Provider Management (Task 018-K.3).
"""
import json
from pathlib import Path
import sys
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuickControls2 import QQuickStyle

from core.events import EVEventBus
from core.models import EVState
from core.provider_config import AIProviderConfig, AIProviderConfigStore, DPAPICredentialStore
from gui.bridge import GuiBridge

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_ROOT = PROJECT_ROOT / "gui" / "qml" / "components"


@pytest.fixture(scope="session")
def qapp():
    """Ensure one QGuiApplication exists."""
    instance = QGuiApplication.instance()
    if instance is None:
        instance = QGuiApplication(sys.argv[:1])
    QQuickStyle.setStyle("Basic")
    return instance


@pytest.fixture
def isolated_bridge(tmp_path: Path):
    """Create a GuiBridge backed by an isolated temporary config store."""
    conf_path = tmp_path / "ai_providers.json"
    cred_path = tmp_path / "ai_credentials.bin"
    cred_store = DPAPICredentialStore(store_path=cred_path)
    store = AIProviderConfigStore(config_path=conf_path, credential_store=cred_store)

    bus = EVEventBus(initial_state=EVState.IDLE)
    bridge = GuiBridge(bus)
    bridge.set_provider_config_store(store)
    style_path = tmp_path / "core_style.json"
    with patch.object(bridge, "_get_core_style_path", return_value=style_path):
        yield bridge
    bridge.shutdown()


def test_topbar_has_settings_button_and_object_name():
    """Verify EVTopBar.qml defines the settings button with objectName 'settingsButton'."""
    content = (COMPONENT_ROOT / "EVTopBar.qml").read_text(encoding="utf-8")
    assert 'objectName: "settingsButton"' in content
    assert 'guiBridge.toggleSettings()' in content


def test_bridge_settings_toggle(isolated_bridge):
    """Verify settings visibility toggles, opens, and closes correctly."""
    bridge = isolated_bridge
    assert bridge.settingsVisible is False

    bridge.toggleSettings()
    assert bridge.settingsVisible is True

    bridge.toggleSettings()
    assert bridge.settingsVisible is False

    bridge.openSettings()
    assert bridge.settingsVisible is True

    bridge.closeSettings()
    assert bridge.settingsVisible is False


def test_bridge_provider_list_json_and_masked_keys(isolated_bridge):
    """Verify provider list is returned as valid JSON with masked keys."""
    bridge = isolated_bridge
    raw_json = bridge.getProvidersJson()
    providers = json.loads(raw_json)

    assert isinstance(providers, list)
    assert len(providers) >= 5

    # Invariant: exactly one provider is active
    active = [p for p in providers if p.get("is_active")]
    assert len(active) == 1

    # Verify keys are never exposed in plaintext
    for p in providers:
        assert "api_key" not in p
        if p.get("has_credential"):
            assert p.get("masked_key") == "••••••••••••"


def test_bridge_set_active_provider(isolated_bridge):
    """Verify active provider can be switched from the bridge."""
    bridge = isolated_bridge
    providers = json.loads(bridge.getProvidersJson())
    first_id = providers[0]["id"]
    second_id = providers[1]["id"]

    bridge.setActiveProvider(second_id)
    updated = json.loads(bridge.getProvidersJson())
    active = [p for p in updated if p.get("is_active")]
    assert len(active) == 1
    assert active[0]["id"] == second_id
    assert bridge.activeProviderName == active[0]["name"]


def test_bridge_save_custom_provider(isolated_bridge):
    """Verify custom OpenAI-compatible provider can be saved and retrieved via bridge."""
    bridge = isolated_bridge
    custom_payload = {
        "id": "custom-my-ai",
        "name": "My Custom Model",
        "provider_type": "Custom / OpenAI Compatible",
        "protocol": "openai_compatible",
        "model": "deepseek-coder",
        "base_url": "https://ai.example.com/v1",
        "enabled": True,
        "is_active": False,
    }

    saved_id = bridge.saveProvider(json.dumps(custom_payload), "my-super-secret-key-1234")
    assert saved_id == "custom-my-ai"

    providers = json.loads(bridge.getProvidersJson())
    matched = [p for p in providers if p["id"] == "custom-my-ai"]
    assert len(matched) == 1
    assert matched[0]["name"] == "My Custom Model"
    assert matched[0]["has_credential"] is True
    assert matched[0]["masked_key"] == "••••••••••••"


def test_bridge_test_connection_reporting(isolated_bridge):
    """Verify bridge.testConnection returns structured JSON with success and message."""
    bridge = isolated_bridge
    test_payload = {
        "id": "test-gemini",
        "name": "Gemini",
        "provider_type": "Gemini",
        "protocol": "gemini",
        "model": "gemini-2.5-flash",
    }

    # With mocked 200 response
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    with patch("httpx.Client.get", return_value=mock_resp):
        res_str = bridge.testConnection(json.dumps(test_payload), "AIzaSyFakeKey")
        res = json.loads(res_str)
        assert res["success"] is True
        assert "✓ Connection successful" in res["message"]

    # With mocked 401 response
    mock_resp_401 = MagicMock()
    mock_resp_401.status_code = 401
    with patch("httpx.Client.get", return_value=mock_resp_401):
        res_str = bridge.testConnection(json.dumps(test_payload), "invalid-key")
        res = json.loads(res_str)
        assert res["success"] is False
        assert "✕ Authentication failed" in res["message"]


def test_qml_settings_overlay_instantiates(qapp, isolated_bridge):
    """Verify EVSettingsOverlay.qml instantiates with no QML errors."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", isolated_bridge)

    component = QQmlComponent(
        engine,
        QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVSettingsOverlay.qml")),
    )
    assert not component.isError(), [e.toString() for e in component.errors()]
    instance = component.create(engine.rootContext())
    assert instance is not None

    qapp.processEvents()
    instance.deleteLater()
    engine.deleteLater()
    qapp.processEvents()


def test_core_style_persistence_and_switching(isolated_bridge, tmp_path: Path):
    """Verify Core style presets can be switched and persisted to disk."""
    bridge = isolated_bridge
    # Mock _get_core_style_path to use tmp_path
    mock_style_file = tmp_path / "core_style.json"
    with patch.object(bridge, "_get_core_style_path", return_value=mock_style_file):
        received_presets = []
        bridge.stylePresetChanged.connect(received_presets.append)

        bridge.setStylePreset("ORIGINAL")
        assert bridge.stylePreset == "ORIGINAL"
        assert "ORIGINAL" in received_presets
        assert mock_style_file.exists()
        saved = json.loads(mock_style_file.read_text(encoding="utf-8"))
        assert saved.get("preset") == "ORIGINAL"

        # Switch to ASTRA
        bridge.setStylePreset("ASTRA")
        assert bridge.stylePreset == "ASTRA"
        assert "ASTRA" in received_presets
        saved = json.loads(mock_style_file.read_text(encoding="utf-8"))
        assert saved.get("preset") == "ASTRA"


def test_available_style_presets_contract(isolated_bridge):
    """Verify availableStylePresets exposes the 5 required presets and descriptions."""
    bridge = isolated_bridge
    presets = bridge.availableStylePresets
    assert isinstance(presets, list)
    preset_ids = [p["id"] for p in presets]
    assert "ASTRA" in preset_ids
    assert "ORIGINAL" in preset_ids
    assert "MINIMAL" in preset_ids
    assert "AMBIENT" in preset_ids
    assert "FOCUSED" in preset_ids

    # Verify descriptions
    descriptions = {p["id"]: p["description"] for p in presets}
    assert "Celestial intelligence globe" in descriptions["ASTRA"]
    assert "Original E.V. intelligence field" in descriptions["ORIGINAL"]


def test_only_one_core_active_in_intelligence_core(qapp, isolated_bridge):
    """Verify EVIntelligenceCore renders exactly one 3D core via Loader."""
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("guiBridge", isolated_bridge)

    component = QQmlComponent(
        engine,
        QUrl.fromLocalFile(str(COMPONENT_ROOT / "EVIntelligenceCore.qml")),
    )
    assert not component.isError(), [e.toString() for e in component.errors()]
    instance = component.create(engine.rootContext())
    assert instance is not None
    qapp.processEvents()

    # Verify initial theme is ASTRA
    isolated_bridge.setStylePreset("ASTRA")
    qapp.processEvents()
    source1 = str(instance.property("presetSource"))
    assert "EVCoreFlagshipVisual.qml" in source1

    # Switch to ORIGINAL
    isolated_bridge.setStylePreset("ORIGINAL")
    qapp.processEvents()
    source2 = str(instance.property("presetSource"))
    assert "EVCoreNexusSphere.qml" in source2 or "EVCoreOriginalVisual.qml" in source2
    # Only one visual loader source is active
    assert source1 != source2

    instance.deleteLater()
    engine.deleteLater()
    qapp.processEvents()

