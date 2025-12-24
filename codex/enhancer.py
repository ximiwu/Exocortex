from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path

from codex.run_codex import run_codex, run_gemini

GEMINI_PROMPT = "开始改进，这是需要改进的文件 @output/main.md，这是用来改进的补充文件 @input/supplement.md"

def _ensure_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        return
    if not source.is_file():
        raise FileNotFoundError(f"Required file not found: {source}")
    shutil.copy2(source, destination)


def main() -> int:
    codex_root = Path(__file__).resolve().parent / "enhancer"
    if not codex_root.is_dir():
        logging.error("codex/enhancer directory not found: %s", codex_root)
        return 1

    input_dir = codex_root / "input"
    output_dir = codex_root / "output"
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    main_md = output_dir / "main.md"
    supplement_md = input_dir / "supplement.md"
    main_py = output_dir / "main.py"
    gemini_md = input_dir / "output_gemini.md"

    try:
        if not main_md.is_file():
            _ensure_file(main_py, main_md)
        if not supplement_md.is_file():
            _ensure_file(gemini_md, supplement_md)
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1

    try:
        run_gemini(
            GEMINI_PROMPT,
            codex_root,
            model="gemini-3-pro-preview",
            new_console=True,
        )
    except FileNotFoundError:
        logging.error("`gemini` command not found. Ensure it is installed and on PATH.")
        return 1
    except subprocess.CalledProcessError as exc:
        logging.error("gemini exited with code %s", exc.returncode)
        return exc.returncode or 1
    except Exception:
        logging.exception("Unhandled error while launching gemini.")
        return 1

    if not main_md.is_file():
        logging.error("enhancer output not found at %s", main_md)
        return 1

    logging.info("Enhancer completed; output written to %s", main_md)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
