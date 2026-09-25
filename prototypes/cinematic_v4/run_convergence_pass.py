"""Run a single convergence pass and capture results."""
import json
import subprocess
import sys
from pathlib import Path

EVIDENCE = Path(__file__).parent / "evidence" / "convergence"

def run_pass(pass_num, orbit_time, yaw, capture_name):
    """Run one capture with given parameters."""
    cmd = [
        sys.executable, "-m", "prototypes.cinematic_v4.run_preview",
        "--size", "1920x1080",
        "--reference-dpi",
        "--freeze",
        "--quality",
        "--orbit-time", str(orbit_time),
        "--view-yaw", str(yaw),
        "--capture", f"{capture_name}.png",
        "--capture-after", "2",
        "--report", f"pass{pass_num}_report.json",
    ]
    print(f"Running pass {pass_num}: t={orbit_time}, yaw={yaw}")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    report_path = EVIDENCE / f"pass{pass_num}_report.json"
    report_path.write_text(result.stdout)
    return result.stdout.strip()

def main():
    print("=" * 60)
    print("CONVERGENCE TUNING - PASS 1")
    print("=" * 60)

    # Full t0/t20/t40 coverage
    for t in [0, 20, 40]:
        run_pass(1, t, 0, f"pass1_t{t}_yaw0")

    # Yaw coverage at t0
    for yaw in [-15, 0, 15]:
        run_pass(1, 0, yaw, f"pass1_t0_yaw{yaw}")

    # t20, t40 yaw coverage
    for t in [20, 40]:
        for yaw in [-15, 15]:
            run_pass(1, t, yaw, f"pass1_t{t}_yaw{yaw}")

    print("\nPass 1 complete.")

if __name__ == "__main__":
    main()
