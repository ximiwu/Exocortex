from __future__ import annotations

from pathlib import Path

from assets_manager import (
    ask_re_tutor as _ask_re_tutor,
    ask_tutor as _ask_tutor,
    asset_init as _asset_init,
    bug_finder as _bug_finder,
    create_student_note as _create_student_note,
    fix_latex as _fix_latex,
    group_dive_in as _group_dive_in,
    integrate as _integrate,
)
from exocortex_core.contracts import AssetInitResult
from exocortex_core.workflow_events import WorkflowEventCallback


def asset_init(
    pdf_path: str | Path,
    *,
    asset_name: str,
    progress_callback,
    rendered_pdf_path: str | Path | None = None,
    event_callback: WorkflowEventCallback | None = None,
) -> AssetInitResult:
    return _asset_init(
        pdf_path=pdf_path,
        asset_name=asset_name,
        progress_callback=progress_callback,
        rendered_pdf_path=rendered_pdf_path,
        event_callback=event_callback,
    )


def group_dive_in(
    asset_name: str,
    group_idx: int,
    *,
    on_secondary_ready=None,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    return _group_dive_in(
        asset_name=asset_name,
        group_idx=group_idx,
        on_secondary_ready=on_secondary_ready,
        event_callback=event_callback,
    )


def ask_tutor(
    question: str,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    return _ask_tutor(
        question,
        asset_name,
        group_idx,
        tutor_idx,
        event_callback=event_callback,
    )


def ask_re_tutor(
    question: str,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    return _ask_re_tutor(
        question,
        asset_name,
        group_idx,
        tutor_idx,
        event_callback=event_callback,
    )


def integrate(
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    return _integrate(
        asset_name,
        group_idx,
        tutor_idx,
        event_callback=event_callback,
    )


def bug_finder(
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    return _bug_finder(
        asset_name,
        group_idx,
        tutor_idx,
        event_callback=event_callback,
    )


def create_student_note(
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    return _create_student_note(
        asset_name,
        group_idx,
        tutor_idx,
        event_callback=event_callback,
    )


def fix_latex(
    markdown_path: str | Path,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    return _fix_latex(
        markdown_path,
        event_callback=event_callback,
    )


__all__ = [
    "ask_re_tutor",
    "ask_tutor",
    "asset_init",
    "bug_finder",
    "create_student_note",
    "fix_latex",
    "group_dive_in",
    "integrate",
]
