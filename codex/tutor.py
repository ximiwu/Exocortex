from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from codex.run_codex import run_gemini



def main(question: str) -> int:
    if "__compiled__" in globals():
        codex_base_dir = Path(sys.argv[0]).resolve().parent / "codex"
    else:
        codex_base_dir = Path(__file__).resolve().parent
    codex_root = codex_base_dir / "tutor"
    if not codex_root.is_dir():
        logging.error("codex/tutor directory not found: %s", codex_root)
        return 1

    if not question.strip():
        logging.error("Question text is required.")
        return 1

    prompt = question
    output_dir = codex_root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_gemini(
            prompt,
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

    logging.info("gemini started for tutor.")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Launch gemini tutor with a question prompt.")
    parser.add_argument(
        "question",
        nargs="+",
        help="Question text to append after the input.md reference.",
    )
    args = parser.parse_args()
    sys.exit(main(" ".join(args.question)))
