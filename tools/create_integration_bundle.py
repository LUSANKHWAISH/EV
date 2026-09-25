"""
Build Script: Generates clean, secret-free EV_Core_Integration_Bundle.zip.
Includes all necessary source code, QML presets, models, build definitions, and tests.
Excludes git, venv, caches, backups, logs, and sensitive data.
"""
import os
import zipfile
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = ROOT_DIR / "EV_Core_Integration_Bundle.zip"

INCLUDE_DIRS = [
    "core",
    "gui",
    "providers",
    "tests",
    "tools",
    "models/wakeword",
]

INCLUDE_ROOT_FILES = [
    "requirements.txt",
    ".env.example",
    "pytest.ini",
    "README.md",
    "CMakeLists.txt",
    "INTEGRATION_GUIDE.md",
]

EXCLUDE_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".log", ".tmp", ".bak", ".backup", ".db", ".orig"
}

EXCLUDE_DIR_NAMES = {
    "__pycache__", ".pytest_cache", ".git", ".venv", "venv", ".agents", ".claude",
    ".locks", "node_modules", "dist", "build"
}

def create_bundle():
    print(f"Building integration bundle from {ROOT_DIR}...")
    total_files = 0
    total_bytes = 0

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Add specific root files
        for fname in INCLUDE_ROOT_FILES:
            fpath = ROOT_DIR / fname
            if fpath.is_file():
                arcname = fname.replace("\\", "/")
                zf.write(fpath, arcname)
                total_files += 1
                total_bytes += fpath.stat().st_size
                print(f"  + Added file: {arcname}")

        # 2. Add directories
        for dir_rel in INCLUDE_DIRS:
            dir_path = ROOT_DIR / dir_rel
            if not dir_path.exists():
                print(f"  ! Warning: {dir_rel} does not exist")
                continue

            for root, dirs, files in os.walk(dir_path):
                # Prune excluded directories
                dirs[:] = [
                    d for d in dirs
                    if d not in EXCLUDE_DIR_NAMES and not d.startswith("backup_") and not d.startswith("gui_backup_")
                ]

                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext in EXCLUDE_EXTENSIONS or file.endswith("~") or file.endswith(".txt"):
                        # Skip temporary files and text dumps
                        if file not in ("requirements.txt", "CMakeLists.txt"):
                            continue

                    full_path = Path(root) / file
                    rel_path = full_path.relative_to(ROOT_DIR)
                    arcname = str(rel_path).replace("\\", "/")

                    zf.write(full_path, arcname)
                    total_files += 1
                    total_bytes += full_path.stat().st_size

    zip_size = OUTPUT_ZIP.stat().st_size
    print(f"\nSuccessfully created {OUTPUT_ZIP.name}:")
    print(f"  Files: {total_files}")
    print(f"  Uncompressed Size: {total_bytes / (1024 * 1024):.2f} MB")
    print(f"  Compressed ZIP Size: {zip_size / (1024 * 1024):.2f} MB")

    # Verify critical components
    with zipfile.ZipFile(OUTPUT_ZIP, "r") as zf:
        namelist = set(zf.namelist())
        critical = [
            "gui/app.py",
            "gui/bridge.py",
            "gui/qml/components/EVIntelligenceCore.qml",
            "gui/qml/components/presets/EVCoreNexusSphere.qml",
            "gui/qml/components/presets/EVCoreFlagshipVisual.qml",
            "core/action_pipeline.py",
            "core/orchestrator.py",
            "core/brain_router.py",
            "models/wakeword/hey_ev.onnx",
            "requirements.txt",
            ".env.example",
        ]
        print("\nVerification of critical files in bundle:")
        for c in critical:
            status = "OK" if c in namelist else "MISSING"
            print(f"  [{status}] {c}")

if __name__ == "__main__":
    create_bundle()
