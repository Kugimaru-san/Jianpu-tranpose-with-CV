#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List


def run_cmd(cmd: List[str], cwd: Optional[Path] = None) -> None:
    print("\n[RUN]", " ".join(cmd))

    # Capture as BYTES to avoid Windows console encoding issues (GBK/CP936).
    p = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False  # <-- important: bytes, not str
    )

    # Decode safely (replace any weird bytes)
    stdout = p.stdout.decode("utf-8", errors="replace") if p.stdout else ""
    stderr = p.stderr.decode("utf-8", errors="replace") if p.stderr else ""

    if stdout.strip():
        print("[STDOUT]\n" + stdout)
    if stderr.strip():
        print("[STDERR]\n" + stderr)

    if p.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {p.returncode}")



def newest_export(out_dir: Path) -> Path:
    candidates = (
        list(out_dir.rglob("*.mxl")) +
        list(out_dir.rglob("*.musicxml")) +
        list(out_dir.rglob("*.xml"))
    )
    if not candidates:
        raise RuntimeError(f"No MusicXML export found under: {out_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime)


def newest_omr_book(out_dir: Path) -> Path:
    books = list(out_dir.rglob("*.omr"))
    if not books:
        # Some Windows setups show OMR book as "OMR book file" without extension in Explorer,
        # but on disk it is still usually .omr. If not found, list everything for debugging.
        created = [str(p) for p in out_dir.rglob("*")]
        sample = "\n".join(created[:120])
        raise RuntimeError(f"No .omr book found under: {out_dir}\nCreated files:\n{sample}")
    return max(books, key=lambda p: p.stat().st_mtime)



def build_job_json(job_path: Path, score_in: Path, out_mxl: Path, out_pdf: Path, plugin_qml: Path) -> None:
    job = [
        {
            "in": str(score_in),
            "plugin": str(plugin_qml),
            "out": [str(out_mxl), str(out_pdf)]
        }
    ]
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="PDF -> Audiveris -> MuseScore plugin -> MXL+PDF")
    ap.add_argument("--pdf-in", required=True, type=Path, help="Input PDF path")
    ap.add_argument("--out-mxl", required=True, type=Path, help="Output .mxl path")
    ap.add_argument("--out-pdf", required=True, type=Path, help="Output .pdf path")

    ap.add_argument("--audiveris-exe", required=True, type=Path, help="Path to Audiveris.exe")
    ap.add_argument("--musescore-exe", required=True, type=Path, help="Path to MuseScore4.exe")
    ap.add_argument("--plugin-qml", required=True, type=Path, help="Path to AddSolfaLyricsLaMinor.qml")

    ap.add_argument("--force", action="store_true", help="Audiveris -force")
    ap.add_argument("--no-opus", action="store_true", help="Disable OPUS export option")
    args = ap.parse_args()

    pdf_in = args.pdf_in.resolve()
    if not pdf_in.exists():
        raise SystemExit(f"PDF not found: {pdf_in}")

    audiveris_exe = args.audiveris_exe.resolve()
    musescore_exe = args.musescore_exe.resolve()
    plugin_qml = args.plugin_qml.resolve()

    for p, label in [(audiveris_exe, "Audiveris.exe"), (musescore_exe, "MuseScore.exe"), (plugin_qml, "plugin qml")]:
        if not p.exists():
            raise SystemExit(f"{label} not found: {p}")

    out_mxl = args.out_mxl.resolve()
    out_pdf = args.out_pdf.resolve()
    out_mxl.parent.mkdir(parents=True, exist_ok=True)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="omr_tmp_") as tmp:
        tmp = Path(tmp)
        aud_out = tmp / "audiveris_out"
        aud_out.mkdir(parents=True, exist_ok=True)

        # --- Audiveris ---
        # --- Audiveris PASS 1: transcribe PDF to .omr book ---
        aud_cmd_1 = [
            str(audiveris_exe),
            "-batch", "-transcribe",
            "-output", str(aud_out),
        ]
        if args.force:
            aud_cmd_1.append("-force")
        aud_cmd_1.append(str(pdf_in))

        run_cmd(aud_cmd_1)

        # Try to find an exported MusicXML directly (sometimes it works in one pass)
        try:
            exported = newest_export(aud_out)
            print(f"[INFO] Audiveris export (single-pass): {exported}")
        except RuntimeError:
            # --- Audiveris PASS 2: export from .omr book to MusicXML ---
            book = newest_omr_book(aud_out)
            print(f"[INFO] Audiveris book found: {book}")

            aud_cmd_2 = [
                str(audiveris_exe),
                "-batch", "-export",
                "-output", str(aud_out),
            ]
            # OPUS option only affects export, so apply it here if you want it
            if not args.no_opus:
                aud_cmd_2 += ["-option", "org.audiveris.omr.sheet.BookManager.useOpus=true"]

            aud_cmd_2.append(str(book))

            run_cmd(aud_cmd_2)

            exported = newest_export(aud_out)
            print(f"[INFO] Audiveris export (two-pass): {exported}")


        # --- MuseScore job.json (plugin + export MXL + PDF) ---
        job_path = tmp / "job.json"
        build_job_json(job_path, exported, out_mxl, out_pdf, plugin_qml)

        ms_cmd = [str(musescore_exe), "-j", str(job_path)]
        run_cmd(ms_cmd, cwd=tmp)

    if not out_mxl.exists():
        raise SystemExit(f"Output MXL not created: {out_mxl}")
    if not out_pdf.exists():
        raise SystemExit(f"Output PDF not created: {out_pdf}")

    print("\n✅ Done")
    print("MXL:", out_mxl)
    print("PDF:", out_pdf)


if __name__ == "__main__":
    main()
