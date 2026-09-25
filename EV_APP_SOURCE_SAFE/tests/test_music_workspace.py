import json

import pytest

from music.workspace import WorkspaceStore, default_layout, validate_layout


def test_default_layout_is_valid_and_collision_free():
    layout = default_layout()
    assert validate_layout(layout)
    assert [panel["preset"] for panel in layout["panels"]] == [
        "ceiling-rain", "flow-trace", "segment-stack"
    ]


@pytest.mark.parametrize(
    "change",
    [
        {"schema": 2},
        {"columns": 0},
        {"panels": []},
        {"panels": [{"id": "x", "preset": "unknown", "x": 0, "y": 0, "w": 1, "h": 1}]},
    ],
)
def test_invalid_layout_is_rejected(change):
    layout = default_layout()
    layout.update(change)
    assert not validate_layout(layout)


def test_overlapping_layout_is_rejected():
    layout = default_layout()
    layout["panels"][1]["y"] = 1
    assert not validate_layout(layout)


def test_store_round_trip_and_corrupt_fallback(tmp_path):
    path = tmp_path / "music_workspace.json"
    store = WorkspaceStore(path)
    store.save(default_layout())
    assert validate_layout(json.loads(path.read_text(encoding="utf-8")))
    path.write_text("{not json", encoding="utf-8")
    assert validate_layout(store.load())
    assert store.load()["layout"] == "reference-trio"


def test_store_keeps_previous_good_layout(tmp_path):
    path = tmp_path / "music_workspace.json"
    store = WorkspaceStore(path)
    store.save(default_layout())
    layout = default_layout()
    layout["panels"][0]["h"] = 1
    store.save(layout)
    path.write_text("bad", encoding="utf-8")
    assert store.load()["panels"][0]["h"] == 2
