"""Capture remaining views for Pass 1."""
import subprocess
import sys
from pathlib import Path

OUT_DIR = Path(r"D:\EV\5.6 sol final round core review")

captures = [
    ("final-round-core-t20.png", 20, 0),
    ("final-round-core-t40.png", 40, 0),
    ("final-round-core-yaw-minus15.png", 0, -15),
    ("final-round-core-yaw-zero.png", 0, 0),
    ("final-round-core-yaw-plus15.png", 0, 15),
]

for capture, t, yaw in captures:
    out = OUT_DIR / capture
    cmd = [
        sys.executable, "run_preview.py",
        "--size", "1920x1080",
        "--reference-dpi",
        "--freeze",
        "--quality",
        "--orbit-time", str(t),
        "--view-yaw", str(yaw),
        "--capture", str(out),
        "--capture-after", "2",
    ]
    print(f"Capturing {out.name}...")
    subprocess.run(cmd, check=False)
    print(f"  Done: {out.exists()}")

print("All captures complete.")
