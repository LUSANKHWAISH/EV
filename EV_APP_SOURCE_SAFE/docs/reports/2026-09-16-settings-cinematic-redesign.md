# Cinematic settings redesign

Status: complete. Restart E.V. once to load the updated settings dialog.

The older green/grey settings window now uses the cinematic interface's dark blue surfaces, warm gold accents, light Segoe UI heading and restrained borders. The panel grows to a maximum 1080×800, with a clearer category rail, larger input fields, matching dropdowns, gold focus states and a prominent Save changes action. The form scrolls at smaller window sizes and all footer actions remain inside the panel.

The style is local to `gui/qml/components/EVSettingsOverlay.qml`; it does not change the global theme or approval design. `prototypes/cinematic_v4/qml/ConnectedWindow.qml` identifies the cinematic context so Core Style explains that its existing presets apply to the classic interface. Existing unfinished settings categories remain placeholders, with clearer wording.

Provider selection, creation, editing, connection testing, activation, deletion, password masking and classic style selection retain the existing GuiBridge routes. No provider service, credential storage, authority, TTS, Music or core-rendering code was changed. The user's provider records and current running app were left untouched.

## Validation

- 10 existing settings tests passed in 4.41 seconds, covering the bridge, provider storage/masking, connection reporting, QML creation and core presets.
- 22 rendered checks passed using the actual settings QML and GuiBridge with a temporary provider/credential store and mocked HTTP. They cover real buttons, saved edits, credential masking, adding/activating/deleting a provider, conditional Azure fields, all category tabs, classic style selection, compact layouts, closing and approval priority.
- Reviewed screenshots at 1920×1080, 1100×760 and 800×600, including an inactive provider with all four footer actions. The dropdown menu uses the same palette as the form. No QML binding or callback errors were reported.

The validation preview uses a fake credential and fixture provider names; it does not demonstrate a live network connection. No FPS benchmark was run for this presentation change.

## Backup and audit

Backup: `D:\EV\.ev-cinematic-nucleus-backups\20260916-201523-before-settings-redesign` — 449 source files copied and SHA256 verified before editing. Final hashes, the source audit, screenshots and validation results are under `D:\EV\prototypes\cinematic_v4\evidence\settings_redesign`. The settings overlay is the one intentionally changed file in the previous protected-source list; the other 351 files remain unchanged. No Git commit was created.

## Next step

Restart E.V., open Interface settings, then AI provider settings. The redesigned dialog opens in the same place and uses the same saved provider configuration.
