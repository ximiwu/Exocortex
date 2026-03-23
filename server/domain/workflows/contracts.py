from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


WorkflowKind = Literal[
    "asset_init",
    "group_dive",
    "ask_tutor",
    "re_tutor",
    "integrate",
    "bug_finder",
    "student_note",
    "fix_latex",
    "compress_preview",
    "compress_execute",
]


@dataclass(frozen=True, slots=True)
class WorkflowCommand:
    kind: WorkflowKind
    asset_name: str | None = None


@dataclass(frozen=True, slots=True, init=False)
class AssetInitCommand(WorkflowCommand):
    source_path: Path
    rendered_pdf_path: Path | None = None
    content_list_path: Path | None = None

    def __init__(
        self,
        *,
        asset_name: str,
        source_path: Path,
        rendered_pdf_path: Path | None = None,
        content_list_path: Path | None = None,
    ) -> None:
        object.__setattr__(self, "kind", "asset_init")
        object.__setattr__(self, "asset_name", asset_name)
        object.__setattr__(self, "source_path", source_path)
        object.__setattr__(self, "rendered_pdf_path", rendered_pdf_path)
        object.__setattr__(self, "content_list_path", content_list_path)


@dataclass(frozen=True, slots=True, init=False)
class GroupDiveCommand(WorkflowCommand):
    group_idx: int

    def __init__(self, *, asset_name: str, group_idx: int) -> None:
        object.__setattr__(self, "kind", "group_dive")
        object.__setattr__(self, "asset_name", asset_name)
        object.__setattr__(self, "group_idx", group_idx)


@dataclass(frozen=True, slots=True, init=False)
class TutorQuestionCommand(WorkflowCommand):
    group_idx: int
    tutor_idx: int
    question: str
    reasoning_effort: Literal["low", "medium", "high", "xhigh"]
    with_global_context: bool

    def __init__(
        self,
        *,
        kind: Literal["ask_tutor", "re_tutor"],
        asset_name: str,
        group_idx: int,
        tutor_idx: int,
        question: str,
        reasoning_effort: Literal["low", "medium", "high", "xhigh"] = "medium",
        with_global_context: bool = True,
    ) -> None:
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "asset_name", asset_name)
        object.__setattr__(self, "group_idx", group_idx)
        object.__setattr__(self, "tutor_idx", tutor_idx)
        object.__setattr__(self, "question", question)
        object.__setattr__(self, "reasoning_effort", reasoning_effort)
        object.__setattr__(self, "with_global_context", with_global_context)


@dataclass(frozen=True, slots=True, init=False)
class ReTutorCommand(TutorQuestionCommand):
    def __init__(self, *, asset_name: str, group_idx: int, tutor_idx: int, question: str) -> None:
        super().__init__(
            kind="re_tutor",
            asset_name=asset_name,
            group_idx=group_idx,
            tutor_idx=tutor_idx,
            question=question,
        )


@dataclass(frozen=True, slots=True, init=False)
class IntegrateCommand(WorkflowCommand):
    group_idx: int
    tutor_idx: int

    def __init__(self, *, asset_name: str, group_idx: int, tutor_idx: int) -> None:
        object.__setattr__(self, "kind", "integrate")
        object.__setattr__(self, "asset_name", asset_name)
        object.__setattr__(self, "group_idx", group_idx)
        object.__setattr__(self, "tutor_idx", tutor_idx)


@dataclass(frozen=True, slots=True, init=False)
class BugFinderCommand(WorkflowCommand):
    group_idx: int
    tutor_idx: int
    manuscript_files: tuple[Path, ...] = ()

    def __init__(
        self,
        *,
        asset_name: str,
        group_idx: int,
        tutor_idx: int,
        manuscript_files: tuple[Path, ...] = (),
    ) -> None:
        object.__setattr__(self, "kind", "bug_finder")
        object.__setattr__(self, "asset_name", asset_name)
        object.__setattr__(self, "group_idx", group_idx)
        object.__setattr__(self, "tutor_idx", tutor_idx)
        object.__setattr__(self, "manuscript_files", manuscript_files)


@dataclass(frozen=True, slots=True, init=False)
class StudentNoteCommand(WorkflowCommand):
    group_idx: int
    tutor_idx: int

    def __init__(self, *, asset_name: str, group_idx: int, tutor_idx: int) -> None:
        object.__setattr__(self, "kind", "student_note")
        object.__setattr__(self, "asset_name", asset_name)
        object.__setattr__(self, "group_idx", group_idx)
        object.__setattr__(self, "tutor_idx", tutor_idx)


@dataclass(frozen=True, slots=True, init=False)
class FixLatexCommand(WorkflowCommand):
    markdown_path: str

    def __init__(self, *, asset_name: str | None, markdown_path: str) -> None:
        object.__setattr__(self, "kind", "fix_latex")
        object.__setattr__(self, "asset_name", asset_name)
        object.__setattr__(self, "markdown_path", markdown_path)


@dataclass(frozen=True, slots=True, init=False)
class CompressCommand(WorkflowCommand):
    fraction_rect: tuple[float, float, float, float]
    ratio: int
    compress_scale: float
    draw_badge: bool
    badge_position: str

    def __init__(
        self,
        *,
        kind: Literal["compress_preview", "compress_execute"],
        asset_name: str,
        fraction_rect: tuple[float, float, float, float],
        ratio: int,
        compress_scale: float,
        draw_badge: bool,
        badge_position: str,
    ) -> None:
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "asset_name", asset_name)
        object.__setattr__(self, "fraction_rect", fraction_rect)
        object.__setattr__(self, "ratio", ratio)
        object.__setattr__(self, "compress_scale", compress_scale)
        object.__setattr__(self, "draw_badge", draw_badge)
        object.__setattr__(self, "badge_position", badge_position)


__all__ = [
    "AssetInitCommand",
    "BugFinderCommand",
    "CompressCommand",
    "FixLatexCommand",
    "GroupDiveCommand",
    "IntegrateCommand",
    "ReTutorCommand",
    "StudentNoteCommand",
    "TutorQuestionCommand",
    "WorkflowCommand",
    "WorkflowKind",
]
