from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Callable

from agent_manager import AgentCallbacks, AgentJob, RunnerConfig, run_agent_job

from .constants import (
    CODEX_MODEL,
    CODEX_REASONING_HIGH,
    ENHANCER_GEMINI_PROMPT,
    GEMINI_MODEL,
    IMG_EXPLAINER_CODEX_PROMPT,
    IMG_EXPLAINER_GEMINI_PROMPT,
    relative_to_repo,
)
from .fs_utils import clean_directory, dir_has_content
from .markdown_utils import clean_markdown_file
from .models import BlockRecord
from .pdf_utils import render_blocks_to_images, stack_images_vertically
from .references import collect_reference_files
from .storage import get_asset_pdf_path, get_group_data_dir, load_block_data, load_group_record


logger = logging.getLogger(__name__)


def select_blocks_for_group(asset_name: str, group_idx: int) -> list[BlockRecord]:
    """Return blocks for the group in the stored selection order."""
    block_data = load_block_data(asset_name)
    if not block_data.blocks:
        raise FileNotFoundError(f"No block data found for asset '{asset_name}'.")

    group_record = load_group_record(asset_name, group_idx)
    block_map = {block.block_id: block for block in block_data.blocks}

    missing: list[int] = []
    selected: list[BlockRecord] = []
    for block_id in group_record.block_ids:
        block = block_map.get(block_id)
        if not block:
            missing.append(block_id)
            continue
        selected.append(block)

    if missing:
        raise ValueError(f"Missing block(s) for asset '{asset_name}', group {group_idx}: {missing}")
    if not selected:
        raise ValueError(f"No blocks found for asset '{asset_name}', group {group_idx}.")

    return selected


def resolve_img_explainer_markdown(img_explainer_dir: Path) -> Path:
    candidates = (
        img_explainer_dir / "enhanced.md",
        img_explainer_dir / "output.md",
        img_explainer_dir / "initial" / "output.md",
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"No img_explainer markdown found under {img_explainer_dir}")


def group_dive_in(
    asset_name: str, group_idx: int, *, on_gemini_ready: Callable[[Path], None] | None = None
) -> Path:
    """
    Generate img_explainer output for a group, archive initial outputs, and run enhancer.
    """
    target_dir = get_group_data_dir(asset_name) / str(group_idx) / "img_explainer_data"
    initial_dir = target_dir / "initial"
    enhanced_md = target_dir / "enhanced.md"

    legacy_output = target_dir / "output.md"
    legacy_gemini = target_dir / "output_gemini.md"
    initial_output = initial_dir / "output.md"
    initial_gemini_output = initial_dir / "output_gemini.md"

    def _run_enhancer() -> Path:
        job = AgentJob(
            name="enhancer",
            runners=[
                RunnerConfig(
                    runner="gemini",
                    prompt_path=ENHANCER_GEMINI_PROMPT,
                    model=GEMINI_MODEL,
                    new_console=True,
                    extra_message=(
                        "以材料 @/output/main.md 的逻辑结构和数学深度 为主轴，将 @/input/supplement.md 中适合插入的片段增量式插入 @/output/main.md ，禁止删减 @/output/main.md的原有内容"
                    ),
                )
            ],
            input_files=[initial_gemini_output],
            input_rename={initial_gemini_output.name: "supplement.md"},
            output_seed_files=[initial_output],
            output_rename={initial_output.name: "main.md"},
            deliver_dir=relative_to_repo(target_dir),
            deliver_rename={"main.md": "enhanced.md"},
            clean_markdown=True,
        )
        run_agent_job(job)
        if not enhanced_md.is_file():
            raise FileNotFoundError(f"enhancer output not found: {enhanced_md}")
        clean_markdown_file(enhanced_md)
        return enhanced_md

    if enhanced_md.is_file():
        clean_markdown_file(enhanced_md)
        logger.info(
            "enhanced.md already exists for asset '%s', group %s; skipping regeneration.",
            asset_name,
            group_idx,
        )
        return enhanced_md

    if legacy_output.is_file() or legacy_gemini.is_file():
        initial_dir.mkdir(parents=True, exist_ok=True)
        if legacy_output.is_file() and not initial_output.is_file():
            shutil.move(str(legacy_output), str(initial_output))
        if legacy_gemini.is_file() and not initial_gemini_output.is_file():
            shutil.move(str(legacy_gemini), str(initial_gemini_output))

    if initial_output.is_file():
        clean_markdown_file(initial_output)
    if initial_gemini_output.is_file():
        try:
            clean_markdown_file(initial_gemini_output)
        except Exception as exc:  # pragma: no cover - defensive cleanup
            logger.warning(
                "Failed to clean existing Gemini output for '%s' (group %s): %s",
                asset_name,
                group_idx,
                exc,
            )
    if initial_output.is_file() and initial_gemini_output.is_file():
        logger.info(
            "Found initial img_explainer outputs for asset '%s', group %s; running enhancer only.",
            asset_name,
            group_idx,
        )
        return _run_enhancer()

    if dir_has_content(target_dir):
        logger.info(
            "img_explainer_data exists for asset '%s', group %s but enhanced.md is missing; regenerating.",
            asset_name,
            group_idx,
        )

    clean_directory(target_dir)
    initial_dir.mkdir(parents=True, exist_ok=True)

    reference_files, reference_rename = collect_reference_files(
        asset_name,
        include_entire_content=True,
    )

    pdf_path = get_asset_pdf_path(asset_name)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found for asset '{asset_name}': {pdf_path}")

    blocks = select_blocks_for_group(asset_name, group_idx)
    images = render_blocks_to_images(pdf_path, blocks, dpi=300)
    merged_image = stack_images_vertically(images)

    thesis_image_path = target_dir / "thesis.png"
    thesis_image_path.parent.mkdir(parents=True, exist_ok=True)
    if not merged_image.save(str(thesis_image_path)):
        raise RuntimeError(f"Failed to save rendered image to {thesis_image_path}")

    def _on_runner_finish(job_name: str, runner: RunnerConfig, workspace: Path, error: Exception | None) -> None:
        if runner.runner != "gemini":
            return
        gemini_output_path = workspace / "output" / "output_gemini.md"
        if not gemini_output_path.is_file():
            logger.warning("Gemini finished but output_gemini.md not found at %s", gemini_output_path)
            return
        try:
            initial_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(gemini_output_path, initial_gemini_output)
            clean_markdown_file(initial_gemini_output)
            if on_gemini_ready is not None:
                on_gemini_ready(initial_gemini_output)
        except Exception as exc:  # pragma: no cover - defensive callback
            logger.warning(
                "Failed to archive Gemini output for '%s' (group %s): %s",
                asset_name,
                group_idx,
                exc,
            )

    callbacks = AgentCallbacks(on_finish=_on_runner_finish)

    job = AgentJob(
        name="img_explainer",
        runners=[
            RunnerConfig(
                runner="codex",
                prompt_path=IMG_EXPLAINER_CODEX_PROMPT,
                model=CODEX_MODEL,
                reasoning_effort=CODEX_REASONING_HIGH,
                new_console=True,
                extra_message="开始讲解 input/thesis.png，保存到 output.md中",
            ),
            RunnerConfig(
                runner="gemini",
                prompt_path=IMG_EXPLAINER_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message="开始讲解 @input/thesis.png，保存到 output_gemini.md中",
            ),
        ],
        input_files=[thesis_image_path],
        input_rename={thesis_image_path.name: "thesis.png"},
        reference_files=reference_files,
        reference_rename=reference_rename,
        deliver_dir=relative_to_repo(initial_dir),
        deliver_rename={
            "output.md": "output.md",
            "output_gemini.md": "output_gemini.md",
        },
        clean_markdown=True,
        callbacks=callbacks,
    )
    run_agent_job(job)

    if not initial_output.is_file():
        raise FileNotFoundError(f"img_explainer output not found: {initial_output}")
    if not initial_gemini_output.is_file():
        raise FileNotFoundError(f"img_explainer Gemini output not found: {initial_gemini_output}")

    return _run_enhancer()

