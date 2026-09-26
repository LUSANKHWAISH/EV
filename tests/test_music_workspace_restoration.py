"""Regression tests for Music workspace visualizer layout persistence and restart-restoration."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from PySide6.QtCore import QEventLoop, QSettings, QTimer, QUrl, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine, QQmlComponent
from PySide6.QtQuick import QQuickItem
from PySide6.QtTest import QTest

from music.session import MusicSession
from music.workspace import (
    DEFAULT_LAYOUT,
    PRESET_LAYOUTS,
    WorkspaceStore,
    get_preset_layout,
    list_preset_layouts,
    validate_layout,
)


def _wait(ms: int = 50) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


class TestWorkspaceStorePersistence:
    """Verifies WorkspaceStore presets, validation, and atomic persistence."""

    def test_all_presets_are_valid_and_non_overlapping(self):
        for name in list_preset_layouts():
            layout = get_preset_layout(name)
            assert validate_layout(layout), f"Preset '{name}' must be valid"
            assert layout["layout"] == name
            assert layout["columns"] == 12
            assert 1 <= len(layout["panels"]) <= 4

    def test_preset_persistence_round_trip(self, tmp_path):
        store_path = tmp_path / "music_workspace.json"
        store = WorkspaceStore(store_path)

        # Save single-trace
        store.save_preset("single-trace")
        loaded = store.load()
        assert loaded["layout"] == "single-trace"
        assert len(loaded["panels"]) == 1
        assert loaded["panels"][0]["preset"] == "flow-trace"

        # Save split-duo
        store.save_preset("split-duo")
        loaded = store.load()
        assert loaded["layout"] == "split-duo"
        assert len(loaded["panels"]) == 2

        # Corrupt file -> fallback to previous good layout
        store_path.write_text("{corrupt json", encoding="utf-8")
        recovered = store.load()
        assert recovered["layout"] == "single-trace"  # from .previous backup


class TestMusicSessionLayoutRestoration:
    """Verifies MusicSession persistence and layout restoration across simulated restarts."""

    def test_restart_restoration(self, tmp_path, monkeypatch):
        store_path = tmp_path / "music_workspace.json"
        settings = QSettings(str(tmp_path / "test_music.ini"), QSettings.Format.IniFormat)

        # Monkeypatch WorkspaceStore default path to test tmp_path
        monkeypatch.setattr(
            "music.session.WorkspaceStore",
            lambda path=None: WorkspaceStore(path or store_path),
        )

        # Session 1: initial run
        session1 = MusicSession(settings=settings)
        assert session1.currentLayout == "reference-trio"
        assert session1.isPanelVisible("ceiling-rain") is True
        assert session1.isPanelVisible("flow-trace") is True
        assert session1.isPanelVisible("segment-stack") is True

        # Switch to single-trace layout and verify
        session1.setLayout("single-trace")
        assert session1.currentLayout == "single-trace"
        assert session1.isPanelVisible("flow-trace") is True
        assert session1.isPanelVisible("ceiling-rain") is False
        assert session1.isPanelVisible("segment-stack") is False
        session1.close()

        # Session 2: simulates app restart
        session2 = MusicSession(settings=settings)
        assert session2.currentLayout == "single-trace", (
            "Layout must be restored after application restart"
        )
        assert session2.isPanelVisible("flow-trace") is True
        assert session2.isPanelVisible("ceiling-rain") is False
        assert session2.isPanelVisible("segment-stack") is False

        # Switch to split-duo
        session2.setLayout("split-duo")
        assert session2.currentLayout == "split-duo"
        assert session2.isPanelVisible("flow-trace") is True
        assert session2.isPanelVisible("segment-stack") is True
        assert session2.isPanelVisible("ceiling-rain") is False
        session2.close()

        # Session 3: simulates another restart
        session3 = MusicSession(settings=settings)
        assert session3.currentLayout == "split-duo"

        # Restore default
        session3.restoreDefaultLayout()
        assert session3.currentLayout == "reference-trio"
        session3.close()

        # Session 4: verify default persisted
        session4 = MusicSession(settings=settings)
        assert session4.currentLayout == "reference-trio"
        session4.close()


class TestVisualizerBoardDynamicLayout:
    """Verifies VisualizerBoard.qml reacts dynamically to layout changes."""

    def test_visualizer_board_visibility_switching(self, tmp_path, monkeypatch):
        store_path = tmp_path / "music_workspace.json"
        settings = QSettings(str(tmp_path / "test_music.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(
            "music.session.WorkspaceStore",
            lambda path=None: WorkspaceStore(path or store_path),
        )

        session = MusicSession(settings=settings)

        engine = QQmlApplicationEngine()
        qml_dir = Path("prototypes/cinematic_v4/qml").resolve()
        engine.addImportPath(str(qml_dir))

        component = QQmlComponent(
            engine,
            QUrl.fromLocalFile(str(qml_dir / "VisualizerBoard.qml")),
        )
        assert not component.isError(), f"QML errors: {component.errors()}"

        board = component.createWithInitialProperties({"music": session})
        assert board is not None

        rain = board.findChild(QQuickItem, "ceilingRain")
        trace = board.findChild(QQuickItem, "flowTrace")
        stack = board.findChild(QQuickItem, "segmentStack")
        span = board.findChild(QQuickItem, "precisionSpectrum")

        assert rain is not None
        assert trace is not None
        assert stack is not None
        assert span is not None

        # 1. reference-trio: all three visible, span hidden
        session.setLayout("reference-trio")
        _wait(50)
        assert rain.isVisible() is True
        assert trace.isVisible() is True
        assert stack.isVisible() is True
        assert span.isVisible() is False

        # 2. studio-span: only span visible
        session.setLayout("studio-span")
        _wait(50)
        assert span.isVisible() is True
        assert rain.isVisible() is False
        assert trace.isVisible() is False
        assert stack.isVisible() is False

        # 3. single-trace: only trace visible
        session.setLayout("single-trace")
        _wait(50)
        assert rain.isVisible() is False
        assert trace.isVisible() is True
        assert stack.isVisible() is False
        assert span.isVisible() is False

        # 4. split-duo: trace and stack visible, rain hidden
        session.setLayout("split-duo")
        _wait(50)
        assert rain.isVisible() is False
        assert trace.isVisible() is True
        assert stack.isVisible() is True
        assert span.isVisible() is False

        # 5. back to reference-trio
        session.setLayout("reference-trio")
        _wait(50)
        assert rain.isVisible() is True
        assert trace.isVisible() is True
        assert stack.isVisible() is True
        assert span.isVisible() is False

        session.close()

    def test_music_workspace_qml_layout_buttons(self, tmp_path, monkeypatch):
        store_path = tmp_path / "music_workspace.json"
        settings = QSettings(str(tmp_path / "test_music.ini"), QSettings.Format.IniFormat)
        monkeypatch.setattr(
            "music.session.WorkspaceStore",
            lambda path=None: WorkspaceStore(path or store_path),
        )

        session = MusicSession(settings=settings)

        engine = QQmlApplicationEngine()
        qml_dir = Path("prototypes/cinematic_v4/qml").resolve()
        engine.addImportPath(str(qml_dir))

        component = QQmlComponent(
            engine,
            QUrl.fromLocalFile(str(qml_dir / "MusicWorkspace.qml")),
        )
        assert not component.isError(), f"QML errors: {component.errors()}"

        workspace = component.createWithInitialProperties({"music": session})
        assert workspace is not None

        trio_btn = workspace.findChild(QQuickItem, "layoutTrioBtn")
        trace_btn = workspace.findChild(QQuickItem, "layoutTraceBtn")
        split_btn = workspace.findChild(QQuickItem, "layoutSplitBtn")
        studio_btn = workspace.findChild(QQuickItem, "layoutStudioBtn")

        assert trio_btn is not None
        assert trace_btn is not None
        assert split_btn is not None
        assert studio_btn is not None

        # Click STUDIO button
        studio_btn.clicked.emit()
        _wait(50)
        assert session.currentLayout == "studio-span"

        # Click TRACE button
        trace_btn.clicked.emit()
        _wait(50)
        assert session.currentLayout == "single-trace"

        # Click SPLIT button
        split_btn.clicked.emit()
        _wait(50)
        assert session.currentLayout == "split-duo"

        # Click TRIO button
        trio_btn.clicked.emit()
        _wait(50)
        assert session.currentLayout == "reference-trio"

        session.close()
