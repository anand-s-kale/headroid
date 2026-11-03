# Copyright 2026 Anand S Kale and the headroid contributors
# SPDX-License-Identifier: Apache-2.0
"""Builds the headroid wheel with the device-server jar bundled inside.

    cd device-server && ./gradlew :server:headroidJar
    cd packages/headroid && python scripts/build_wheel.py [--jar PATH] [--outdir dist]

Needs `pip install build`.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PKG_DIR = Path(__file__).resolve().parents[1]
REPO = PKG_DIR.parents[1]
DEFAULT_JAR = REPO / "device-server" / "server" / "build" / "headroid" / "headroid-server.jar"
DEST = PKG_DIR / "src" / "headroid" / "_server" / "headroid-server.jar"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jar", default=str(DEFAULT_JAR))
    ap.add_argument("--outdir", default=str(PKG_DIR / "dist"))
    args = ap.parse_args(argv)

    jar = Path(args.jar)
    if not jar.is_file():
        print(
            f"error: server jar not found at {jar}\n"
            "build it first: cd device-server && ./gradlew :server:headroidJar "
            "(or pass --jar PATH)",
            file=sys.stderr,
        )
        return 1
    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(jar, DEST)
    print(f"copied {jar} -> {DEST}")
    proc = subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", args.outdir],
        cwd=PKG_DIR,
        check=False,
    )
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
