from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .constants import ASSETS_ROOT


def resolve_asset_img2md_output_markdown(asset_name: str) -> Path:
    candidates = (
        ASSETS_ROOT / asset_name / "img2md_output" / "output.md",
        ASSETS_ROOT / asset_name / "img2mg_output" / "output.md",
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"img2md output.md not found for asset '{asset_name}'; tried: "
        + ", ".join(str(path) for path in candidates)
    )


def collect_reference_files(
    asset_name: str,
    *,
    reference_filenames: Iterable[str] | None = None,
    include_entire_content: bool = False,
    entire_content_filename: str = "entire_content.md",
) -> tuple[list[Path], dict[str, str]]:
    asset_reference_dir = ASSETS_ROOT / asset_name / "references"
    if not asset_reference_dir.is_dir():
        raise FileNotFoundError(
            f"References directory not found for asset '{asset_name}': {asset_reference_dir}"
        )

    sources: list[Path] = []
    if reference_filenames is None:
        for path in asset_reference_dir.iterdir():
            if path.is_file():
                sources.append(path)
    else:
        for filename in reference_filenames:
            source = asset_reference_dir / filename
            if not source.is_file():
                raise FileNotFoundError(f"Missing reference file for asset '{asset_name}': {source}")
            sources.append(source)

    rename: dict[str, str] = {}
    if include_entire_content:
        entire_content_source = resolve_asset_img2md_output_markdown(asset_name)
        sources.append(entire_content_source)
        if entire_content_source.name != entire_content_filename:
            rename[entire_content_source.name] = entire_content_filename

    if not sources:
        raise FileNotFoundError(f"No reference files found in {asset_reference_dir}")

    return sources, rename

