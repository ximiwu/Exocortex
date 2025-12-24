from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

from codex.run_codex import run_codex

def main(question: str) -> int:
    if "__compiled__" in globals():
        codex_base_dir = Path(sys.argv[0]).resolve().parent / "codex"
    else:
        codex_base_dir = Path(__file__).resolve().parent
    codex_root = codex_base_dir / "integrator"
    if not codex_root.is_dir():
        logging.error("codex/integrator directory not found: %s", codex_root)
        return 1

    if not question.strip():
        logging.error("Question text is required.")
        return 1

    prompt = "start integrate"
    try:
        run_codex(
            prompt,
            codex_root,
            model="gpt-5.2",
            model_reasoning_effort="high",
            new_console=True,
        )
    except FileNotFoundError:
        logging.error("`codex` command not found. Ensure it is installed and on PATH.")
        return 1
    except subprocess.CalledProcessError as exc:
        logging.error("codex exited with code %s", exc.returncode)
        return exc.returncode or 1
    except Exception:
        logging.exception("Unhandled error while launching codex.")
        return 1

    logging.info("codex started for integrator.")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Launch codex integrator with a question prompt.")
    parser.add_argument(
        "question",
        nargs="+",
        help="Question text to append after the input.md reference.",
    )
    args = parser.parse_args()
    sys.exit(main(" ".join(args.question)))
