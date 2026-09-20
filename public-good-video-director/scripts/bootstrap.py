#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import re
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = SKILL_ROOT / "assets" / "runtime"


def main() -> int:
    parser = argparse.ArgumentParser(description="Install the portable public-good video runtime.")
    parser.add_argument("destination", help="Destination studio directory.")
    parser.add_argument("--install", action="store_true", help="Create .venv and install Python/Node dependencies.")
    parser.add_argument("--local-speech", action="store_true", help="Also install Edge TTS and local alignment dependencies.")
    parser.add_argument("--kokoro", action="store_true", help="Also install the larger fully-local Kokoro Chinese stack.")
    parser.add_argument("--force", action="store_true", help="Replace an existing destination.")
    args = parser.parse_args()

    destination = Path(args.destination).expanduser().resolve()
    if destination.exists():
        if not args.force:
            raise SystemExit(f"Destination already exists: {destination}")
        shutil.rmtree(destination)
    shutil.copytree(TEMPLATE, destination)
    (destination / "projects").mkdir(exist_ok=True)

    if args.install:
        node = shutil.which("node")
        if not node:
            raise SystemExit("Node.js 22 or newer is required for HyperFrames rendering.")
        version = subprocess.run([node, "--version"], check=True, capture_output=True, text=True).stdout.strip()
        match = re.match(r"v?(\d+)", version)
        if not match or int(match.group(1)) < 22:
            raise SystemExit(f"Node.js 22 or newer is required; found {version}.")
        subprocess.run([sys.executable, "-m", "venv", str(destination / ".venv")], check=True)
        python = destination / ".venv" / "bin" / "python"
        if sys.platform == "win32":
            python = destination / ".venv" / "Scripts" / "python.exe"
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(destination / "requirements.txt")], check=True)
        if args.local_speech:
            subprocess.run([str(python), "-m", "pip", "install", "-r", str(destination / "requirements-edge-align.txt")], check=True)
        if args.kokoro:
            subprocess.run([str(python), "-m", "pip", "install", "-r", str(destination / "requirements-kokoro.txt")], check=True)
        pnpm = shutil.which("pnpm")
        if pnpm:
            subprocess.run([pnpm, "install"], cwd=destination, check=True)
        else:
            print("pnpm not found; install pnpm before rendering.", file=sys.stderr)
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
