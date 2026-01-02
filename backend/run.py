#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict


def load_dotenv(dotenv_path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not dotenv_path.exists():
        return env
    for raw in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def main() -> None:
    ap = argparse.ArgumentParser(description="Convenience runner (loads .env) for OMR pipeline")
    ap.add_argument("--pdf-in", required=True, type=Path, help="Input PDF path")
    ap.add_argument("--out-dir", type=Path, default=Path("output"), help="Directory for outputs")
    ap.add_argument("--dotenv", type=Path, default=Path(".env"), help="Path to .env (default: ./backend/.env)")
    args = ap.parse_args()

    # Ensure we load .env from the same folder as this script by default
    script_dir = Path(__file__).parent.resolve()
    dotenv_path = (script_dir / args.dotenv).resolve() if not args.dotenv.is_absolute() else args.dotenv.resolve()
    env = load_dotenv(dotenv_path)

    audiveris_exe = env.get("AUDIVERIS_EXE")
    musescore_exe = env.get("MUSESCORE_EXE")
    plugin_qml = env.get("JIANPU_QML")

    if not (audiveris_exe and musescore_exe and plugin_qml):
        raise SystemExit(
            "Missing one of these keys in .env:\n"
            "  AUDIVERIS_EXE\n"
            "  MUSESCORE_EXE\n"
            "  JIANPU_QML\n"
            f"Loaded from: {dotenv_path}"
        )

    pdf_in = args.pdf_in.resolve()
    if not pdf_in.exists():
        raise SystemExit(f"PDF not found: {pdf_in}")

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    out_mxl = out_dir / f"{pdf_in.stem}_jianpu.mxl"
    out_pdf = out_dir / f"{pdf_in.stem}_jianpu.pdf"

    main_py = script_dir / "main.py"
    cmd = [
        sys.executable, str(main_py),
        "--pdf-in", str(pdf_in),
        "--out-mxl", str(out_mxl),
        "--out-pdf", str(out_pdf),
        "--audiveris-exe", audiveris_exe,
        "--musescore-exe", musescore_exe,
        "--plugin-qml", plugin_qml,
    ]

    print("\n[RUN]", " ".join(cmd))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
