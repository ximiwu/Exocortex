from __future__ import annotations

import logging
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from codex.run_codex import run_codex, run_gemini

CODEX_PROMPT = (
    "开始讲解 [thesis.png](input/thesis.png) ，以下是供参考的references: "
    "[background.md](references/background.md)  "
    "[formula.md](references/formula.md)  "
    "[concept.md](references/concept.md) [entire_content.md](references/entire_content.md)"
)

GEMINI_PROMPT = (f"开始讲解 @input/thesis.png ，以下是供参考的references:  @references/background.md , @references/formula.md , @references/concept.md。将讲解内容保存至 /output/output_gemini.md")


def _launch_runner(
    name: str,
    launcher: Callable[..., subprocess.CompletedProcess[str]],
    *args,
    on_success: Callable[[], None] | None = None,
    **kwargs,
) -> int:
    try:
        launcher(*args, **kwargs)
        logging.info("%s started for img_explainer.", name)
        if on_success:
            try:
                on_success()
            except Exception:
                logging.exception("on_success callback failed for %s runner.", name)
        return 0
    except FileNotFoundError as exc:
        logging.error("%s", exc)
        return 1
    except subprocess.CalledProcessError as exc:
        logging.error("%s exited with code %s", name, exc.returncode)
        return exc.returncode or 1
    except Exception:
        logging.exception("Unhandled error while launching %s.", name)
        return 1


def main(*, on_gemini_ready: Callable[[Path], None] | None = None) -> int:
    codex_root = Path(__file__).resolve().parent / "img_explainer"
    if not codex_root.is_dir():
        logging.error("codex/img_explainer directory not found: %s", codex_root)
        return 1
    gemini_output_path = codex_root / "output" / "output_gemini.md"

    def _handle_gemini_success() -> None:
        if not on_gemini_ready:
            return
        if not gemini_output_path.is_file():
            logging.warning("Gemini finished but output_gemini.md not found at %s", gemini_output_path)
            return
        on_gemini_ready(gemini_output_path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                _launch_runner,
                "codex",
                run_codex,
                CODEX_PROMPT,
                codex_root,
                model="gpt-5.2",
                model_reasoning_effort="high",
                new_console=True,
            ),
            executor.submit(
                _launch_runner,
                "gemini",
                run_gemini,
                GEMINI_PROMPT,
                codex_root,
                model="gemini-3-pro-preview",
                new_console=True,
                on_success=_handle_gemini_success,
            ),
        ]
        exit_codes = [future.result() for future in futures]

    exit_code = max(exit_codes) if exit_codes else 0
    if exit_code == 0:
        logging.info("codex and gemini started for img_explainer.")
    return exit_code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
