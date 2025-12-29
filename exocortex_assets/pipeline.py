from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Callable

from agent_manager import AgentJob, RunnerConfig, merge_outputs, run_agent_jobs

from .constants import (
    CODEX_MODEL,
    CODEX_REASONING_HIGH,
    EXTRACTOR_AGENTS,
    EXTRACTOR_OUTPUT_NAMES,
    EXTRACTOR_PROMPTS,
    GEMINI_MODEL,
    IMG2MD_GEMINI_PROMPT,
    relative_to_repo,
)
from .fs_utils import clean_directory, copy_raw_pdf, safe_rmtree
from .markdown_utils import clean_markdown_file
from .models import AssetInitResult
from .pdf_utils import convert_pdf_to_images, render_markdown_to_pdf
from .storage import get_asset_dir


logger = logging.getLogger(__name__)


def asset_init(
    pdf_path: str | Path,
    asset_name: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
    *,
    rendered_pdf_path: str | Path | None = None,
) -> AssetInitResult:
    """
    Run the PDF -> image -> markdown -> extractor pipeline for a given asset.

    If the source is a markdown file, skip img2md and use the markdown as output.md.
    """
    source_path = Path(pdf_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    is_markdown = source_path.suffix.lower() == ".md"
    resolved_asset_name = asset_name or source_path.stem
    asset_dir = get_asset_dir(resolved_asset_name)
    references_dir = asset_dir / "references"
    img2md_output_dir = asset_dir / "img2md_output"
    img2md_output_dir.mkdir(parents=True, exist_ok=True)

    def _notify(message: str) -> None:
        if progress_callback:
            try:
                progress_callback(message)
            except Exception:  # pragma: no cover - defensive
                pass

    if is_markdown:
        _notify("Preparing markdown asset...")
        logger.info("Preparing markdown asset '%s' from %s", resolved_asset_name, source_path)
        asset_dir.mkdir(parents=True, exist_ok=True)
        clean_directory(references_dir)

        output_md = img2md_output_dir / "output.md"
        output_md.write_text(
            source_path.read_text(encoding="utf-8-sig"),
            encoding="utf-8",
            newline="\n",
        )
        clean_markdown_file(output_md)

        if rendered_pdf_path is not None:
            rendered_pdf_path = Path(rendered_pdf_path)
            if not rendered_pdf_path.is_file():
                raise FileNotFoundError(f"Rendered PDF not found: {rendered_pdf_path}")
            _notify("Copying rendered PDF...")
            raw_pdf_path = copy_raw_pdf(rendered_pdf_path, asset_dir)
        else:
            _notify("Rendering markdown to PDF...")
            raw_pdf_path = render_markdown_to_pdf(output_md, asset_dir / "raw.pdf")
    else:
        _notify("Copying PDF and preparing directories...")
        logger.info("Preparing asset '%s' from %s", resolved_asset_name, source_path)
        raw_pdf_path = copy_raw_pdf(source_path, asset_dir)
        clean_directory(references_dir)

        images_dir = asset_dir / "img2md_images"
        clean_directory(images_dir)

        _notify("Converting PDF pages to images...")
        image_paths = convert_pdf_to_images(source_path, images_dir, dpi=300)
        if not image_paths:
            raise RuntimeError(f"No images rendered from {source_path}")
        logger.info("Converted %d page(s) to %s", len(image_paths), images_dir)

        _notify("Running img2md...")
        img2md_output_dir.mkdir(parents=True, exist_ok=True)
        stale_pattern = re.compile(r"output_(\d{3})\.md$", re.IGNORECASE)
        for path in img2md_output_dir.iterdir():
            if path.is_file() and stale_pattern.match(path.name):
                path.unlink(missing_ok=True)

        image_pattern = re.compile(r".*_(\d{3})\.png$", re.IGNORECASE)

        def _image_sort_key(path: Path) -> tuple[int, int | str]:
            match = image_pattern.match(path.name)
            if match:
                return 0, int(match.group(1))
            return 1, path.name.lower()

        sorted_images = sorted(image_paths, key=_image_sort_key)

        jobs: list[AgentJob] = []
        for idx, image_path in enumerate(sorted_images):
            match = image_pattern.match(image_path.name)
            suffix = match.group(1) if match else f"{idx + 1:03d}"
            output_name = f"output_{suffix}.md"
            jobs.append(
                AgentJob(
                    name=f"img2md_{suffix}",
                    runners=[
                        RunnerConfig(
                            runner="gemini",
                            prompt_path=IMG2MD_GEMINI_PROMPT,
                            model=GEMINI_MODEL,
                            new_console=True,
                        )
                    ],
                    input_files=[image_path],
                    input_rename={image_path.name: "input.png"},
                    deliver_dir=relative_to_repo(img2md_output_dir),
                    deliver_rename={"output.md": output_name},
                    clean_markdown=True,
                )
            )

        results = run_agent_jobs(jobs, max_workers=len(jobs))
        delivered = [path for result in results for path in result.delivered]
        if not delivered:
            raise FileNotFoundError("img2md produced no outputs")

        merged_output = merge_outputs(
            img2md_output_dir,
            r"output_(\d{3})\.md",
            "output.md",
        )
        clean_markdown_file(merged_output)

        try:
            safe_rmtree(images_dir)
        except Exception:
            logger.warning("Failed to remove temp images directory: %s", images_dir)

    output_md = img2md_output_dir / "output.md"
    if not output_md.is_file():
        raise FileNotFoundError(f"img2md output.md not found for asset '{resolved_asset_name}'")

    _notify("Running extractors...")
    extractor_jobs: list[AgentJob] = []
    for agent_name in EXTRACTOR_AGENTS:
        prompt_path = EXTRACTOR_PROMPTS.get(agent_name)
        output_name = EXTRACTOR_OUTPUT_NAMES[agent_name]
        if prompt_path is None:
            raise FileNotFoundError(f"Missing extractor prompt for {agent_name}")
        extractor_jobs.append(
            AgentJob(
                name=f"extractor_{agent_name}",
                runners=[
                    RunnerConfig(
                        runner="codex",
                        prompt_path=prompt_path,
                        model=CODEX_MODEL,
                        reasoning_effort=CODEX_REASONING_HIGH,
                        new_console=True,
                    )
                ],
                input_files=[output_md],
                input_rename={output_md.name: "input.md"},
                deliver_dir=relative_to_repo(references_dir),
                deliver_rename={output_name: output_name},
                clean_markdown=True,
            )
        )

    extractor_results = run_agent_jobs(extractor_jobs, max_workers=len(extractor_jobs))
    reference_files: list[Path] = [path for result in extractor_results for path in result.delivered]
    if not reference_files:
        raise FileNotFoundError("Extractor produced no reference files")

    logger.info("Moved %d file(s) to %s", len(reference_files), references_dir)
    return AssetInitResult(
        asset_dir=asset_dir,
        references_dir=references_dir,
        raw_pdf_path=raw_pdf_path,
        reference_files=reference_files,
    )

