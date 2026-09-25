# E.V. TASK 011C.4.1 — TRANSPARENT TOP BAR

One-file visual micro-patch.

Only the top-level EVTopBar background changes:

BEFORE
color: Theme.surfaceRaised

AFTER
color: "transparent"

The later Theme.surfaceRaised use for a window-control hover state is preserved.

Unchanged:
- top-bar geometry
- bottom divider
- E.V. title/subtitle
- minimize/maximize/restore/close controls
- all control hover states
- dragging / double-click maximize-restore
- EVWindow / EVFlagshipStage / Theme
- R11Q-D2.3 core
- Python / tests / qmldir
