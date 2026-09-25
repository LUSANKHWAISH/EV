# E.V. TASK 011C.4 — DESIGN TOKENS / VISUAL CONSISTENCY

## Inspection finding

The live GUI already uses Theme.qml extensively. The remaining issue is not a
missing design system; it is inconsistent expression of equivalent values.

Examples found in the live inspection:
- EVWindow gives the top bar 48 px while EVTopBar's own default was 56 px.
- spacingLG/MD/SM duplicate spacingS/XS/XXS.
- window/default/minimum sizes are repeated as raw literals.
- resize hit areas use raw 6/10 pixel values.
- the three window controls repeat identical 40 x 32 geometry.
- visual emphasis values 0.88 / 0.86 / 0.72 / 0.62 / 0.50 are raw literals.
- flagship state tracking uses Theme.letterSpacingWide + 0.35.

## 011C.4 decision

Normalize these values into Theme tokens while preserving the current visible
appearance.

### New Theme tokens
- letterSpacingEmphasis
- windowDefaultWidth / windowDefaultHeight
- windowMinimumWidth / windowMinimumHeight
- stageCompactWidth / stageCompactHeight
- topBarHeight
- windowControlWidth / windowControlHeight
- windowResizeEdgeSize / windowResizeCornerSize
- opacityEmphasis
- opacitySignal
- opacityStandard
- opacityMuted
- opacitySubtle

### Canonical spacing
spacingS / spacingXS / spacingXXS are the canonical tokens.

spacingLG / spacingMD / spacingSM remain in Theme.qml as compatibility aliases,
so older registered components are not broken.

## Important non-changes

This pass does NOT change:
- R11Q-D2.3 EVIntelligenceCore.qml
- EVCoreLattice.qml
- EVCoreRing.qml
- Main.qml
- qmldir
- state colors
- state energy mapping
- motion durations/easing
- typography sizes
- accepted stage information hierarchy
- window behavior
- registered component list
- Python/tests

The top bar remains 48 px in the live EVWindow; the change only makes the
standalone EVTopBar default agree with the value already used by the live shell.
