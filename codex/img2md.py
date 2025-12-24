from __future__ import annotations

import logging
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from codex.run_codex import run_codex

IMAGE_PATTERN = re.compile(r".*_(\d{3})\.png$", re.IGNORECASE)
OUTPUT_PATTERN = re.compile(r"output_(\d{3})\.md$", re.IGNORECASE)


def find_images(input_dir: Path) -> list[Path]:
    """Return input images sorted by the trailing 3-digit suffix."""
    matches = [
        path
        for path in input_dir.iterdir()
        if path.is_file() and IMAGE_PATTERN.match(path.name)
    ]
    return sorted(matches, key=lambda path: int(IMAGE_PATTERN.match(path.name).group(1)))


def find_outputs(output_dir: Path) -> list[Path]:
    """Return output markdown files sorted by the trailing 3-digit suffix."""
    matches = [
        path
        for path in output_dir.iterdir()
        if path.is_file() and OUTPUT_PATTERN.match(path.name)
    ]
    return sorted(matches, key=lambda path: int(OUTPUT_PATTERN.match(path.name).group(1)))


def build_prompt(image: Path) -> str:
    """Construct the codex prompt using the image suffix."""
    match = IMAGE_PATTERN.match(image.name)
    if not match:
        raise ValueError(f"Image name does not contain a 3-digit suffix: {image.name}")
    suffix = match.group(1)
    return (
        f"[{image.name}](input/{image.name}) 开始转换，保存markdown文件至："
        f"output/output_{suffix}.md"
    )


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    codex_dir = repo_root / "codex" / "img2md"
    input_dir = codex_dir / "input"
    output_dir = codex_dir / "output"

    if not codex_dir.is_dir():
        logging.error("codex/img2md directory not found: %s", codex_dir)
        return 1

    if not input_dir.is_dir():
        logging.error("Input directory not found: %s", input_dir)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    images = find_images(input_dir)
    if not images:
        logging.error("No images matched '*_###.png' under %s", input_dir)
        return 1

    logging.info("Found %d image(s); launching codex concurrently.", len(images))

    exit_code = 0
    with ThreadPoolExecutor() as executor:
        futures = {}
        for image in images:
            image_path = (codex_dir / "input" / image.name).resolve()
            prompt = build_prompt(image)
            logging.info("Submitting %s", image_path)
            futures[
                executor.submit(
                    run_codex,
                    prompt,
                    codex_dir,
                    model="gpt-5.2",
                    model_reasoning_effort="medium",
                    new_console=True,
                )
            ] = image

        for future in as_completed(futures):
            image = futures[future]
            try:
                future.result()
            except FileNotFoundError:
                logging.error(
                    "`codex` command not found. Ensure it is installed and on PATH."
                )
                exit_code = exit_code or 1
            except subprocess.CalledProcessError as exc:
                logging.error(
                    "codex exited with code %s for %s", exc.returncode, image.name
                )
                exit_code = exit_code or exc.returncode
            except Exception:
                logging.exception("Unhandled error for %s", image.name)
                exit_code = exit_code or 1

    # Merge generated output_###.md files into output.md in order, then delete them.
    outputs = find_outputs(output_dir)
    if outputs:
        merged_path = output_dir / "output.md"
        try:
            merged_content = "\n\n".join(
                path.read_text(encoding="utf-8") for path in outputs
            )
            merged_path.write_text(
                merged_content + ("\n" if merged_content else ""),
                encoding="utf-8",
            )
        except OSError:
            logging.exception("Failed to merge output files into %s", merged_path)
            exit_code = exit_code or 1
        else:
            for path in outputs:
                try:
                    path.unlink()
                except OSError:
                    logging.warning("Failed to delete %s", path)
            logging.info("Merged %d files into %s", len(outputs), merged_path)
    else:
        logging.error("No output files matched 'output_###.md' under %s", output_dir)
        exit_code = exit_code or 1

    if exit_code == 0:
        logging.info("All images processed.")
    return exit_code


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    sys.exit(main())
