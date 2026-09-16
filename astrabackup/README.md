# Astra backup

This folder holds a local recovery ZIP for the accepted E.V. application and the
Astra planning handoff. The ZIP is deliberately excluded from Git; its SHA-256,
scope and per-file manifest are recorded in `checkpoint.json` and
`source-manifest.json`. Those small records are versioned with this README.

The snapshot includes selected source, runtime graphics/audio assets, launchers,
tests, synthetic audio fixtures and documentation, including inherited integration
work. It does **not** include API keys, OAuth tokens, DPAPI stores, `.env`, runtime
databases, browser profiles, personal recordings, the reference MP4, `.venv`, voice
models, old experiments or previous backup trees. It is a source recovery snapshot,
not a full drive backup or an export of your accounts. Historical Git-tracked files
are retained. Backup metadata files are outside the ZIP to avoid circular hashes;
the ZIP contains its own `ASTRA_ARCHIVE_MANIFEST.json`.

## Verify and restore

From the project directory:

```powershell
$astraRecord = Get-Content .\astrabackup\checkpoint.json -Raw | ConvertFrom-Json
$astraZip = Join-Path .\astrabackup $astraRecord.archive
$astraHash = (Get-FileHash -LiteralPath $astraZip -Algorithm SHA256).Hash.ToLowerInvariant()
if ($astraHash -ne $astraRecord.sha256) { throw 'Backup checksum mismatch' }
# Choose a NEW empty directory. Do not overwrite the running application.
Expand-Archive -LiteralPath $astraZip -DestinationPath D:\EV-astra-restored
```

Inspect `ASTRA_ARCHIVE_MANIFEST.json` for per-file hashes. Create a fresh Python 3.12
environment; use the dependency notes in `ASTRA_HANDOFF.md`. Credentials and voice
models must be configured separately on that machine. Start with the isolated
cinematic preview and unit checks before connecting real accounts or devices.
The ZIP does not contain `.git`; clone the private repository separately if history
is needed. Do not run `git reset --hard` on the only working copy.

Older local backups under `.ev-cinematic-nucleus-backups` remain untouched. A remote
clone contains the recovery instructions/manifest and the committed source, but
not the local recovery ZIP. Copy the ZIP separately if you need an offline copy.
