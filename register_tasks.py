import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent


def build_schtasks_commands(python_exe: str = sys.executable) -> list:
    generate_script = str(PROJECT_DIR / "generate_drafts.py")
    check_script = str(PROJECT_DIR / "check_approvals.py")
    return [
        [
            "schtasks", "/create", "/tn", "BlogAuto_GenerateDrafts",
            "/tr", f'"{python_exe}" "{generate_script}"',
            "/sc", "hourly", "/mo", "2", "/f",
        ],
        [
            "schtasks", "/create", "/tn", "BlogAuto_CheckApprovals",
            "/tr", f'"{python_exe}" "{check_script}"',
            "/sc", "minute", "/mo", "10", "/f",
        ],
    ]


def register(dry_run: bool = False) -> None:
    for cmd in build_schtasks_commands():
        if dry_run:
            print(" ".join(cmd))
        else:
            subprocess.run(cmd, check=True)


if __name__ == "__main__":
    register(dry_run="--dry-run" in sys.argv)
