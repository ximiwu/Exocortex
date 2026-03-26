from __future__ import annotations

from pathlib import Path

from exocortex_core.contracts import AssetInitResult
from exocortex_core.workflow_events import WorkflowEventCallback
from server.legacy import workflows as legacy_workflows

from .contracts import (
    AssetInitCommand,
    BugFinderCommand,
    FlashcardCommand,
    FixLatexCommand,
    GroupDiveCommand,
    IntegrateCommand,
    ReTutorCommand,
    StudentNoteCommand,
    TutorQuestionCommand,
)


def asset_init(
    command: AssetInitCommand,
    *,
    progress_callback,
    event_callback: WorkflowEventCallback | None = None,
) -> AssetInitResult:
    return legacy_workflows.asset_init(
        pdf_path=command.source_path,
        asset_name=command.asset_name,
        progress_callback=progress_callback,
        rendered_pdf_path=command.rendered_pdf_path,
        content_list_path=command.content_list_path,
        event_callback=event_callback,
    )


def group_dive_in(
    command: GroupDiveCommand,
    *,
    on_secondary_ready=None,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    return legacy_workflows.group_dive_in(
        asset_name=command.asset_name,
        group_idx=command.group_idx,
        on_secondary_ready=on_secondary_ready,
        event_callback=event_callback,
    )


def flashcard(command: FlashcardCommand, *, event_callback: WorkflowEventCallback | None = None) -> Path:
    return legacy_workflows.flashcard(
        command.asset_name,
        command.group_idx,
        event_callback=event_callback,
    )


def ask_tutor(command: TutorQuestionCommand, *, event_callback: WorkflowEventCallback | None = None) -> Path:
    return legacy_workflows.ask_tutor(
        command.question,
        command.asset_name,
        command.group_idx,
        command.tutor_idx,
        reasoning_effort=command.reasoning_effort,
        with_global_context=command.with_global_context,
        event_callback=event_callback,
    )


def ask_re_tutor(command: ReTutorCommand, *, event_callback: WorkflowEventCallback | None = None) -> Path:
    return legacy_workflows.ask_re_tutor(
        command.question,
        command.asset_name,
        command.group_idx,
        command.tutor_idx,
        event_callback=event_callback,
    )


def integrate(command: IntegrateCommand, *, event_callback: WorkflowEventCallback | None = None) -> Path:
    return legacy_workflows.integrate(
        command.asset_name,
        command.group_idx,
        command.tutor_idx,
        event_callback=event_callback,
    )


def bug_finder(command: BugFinderCommand, *, event_callback: WorkflowEventCallback | None = None) -> Path:
    return legacy_workflows.bug_finder(
        command.asset_name,
        command.group_idx,
        command.tutor_idx,
        event_callback=event_callback,
    )


def create_student_note(command: StudentNoteCommand, *, event_callback: WorkflowEventCallback | None = None) -> Path:
    return legacy_workflows.create_student_note(
        command.asset_name,
        command.group_idx,
        command.tutor_idx,
        event_callback=event_callback,
    )


def fix_latex(command: FixLatexCommand, *, resolved_markdown_path: Path, event_callback: WorkflowEventCallback | None = None) -> Path:
    return legacy_workflows.fix_latex(
        resolved_markdown_path,
        event_callback=event_callback,
    )


__all__ = [
    "ask_re_tutor",
    "ask_tutor",
    "asset_init",
    "bug_finder",
    "create_student_note",
    "flashcard",
    "fix_latex",
    "group_dive_in",
    "integrate",
]
