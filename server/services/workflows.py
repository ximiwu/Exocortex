from __future__ import annotations

import base64
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from exocortex_core.contracts import AssetInitResult
from exocortex_core.pdf_compress import CompressPreviewResult, compress_pdf_selection, render_compress_preview
from exocortex_core.workflow_events import WorkflowEvent
from server.domain.assets import get_asset_pdf_path
from server.domain.workflows import orchestrator
from server.domain.workflows.contracts import (
    AssetInitCommand,
    BugFinderCommand,
    CompressCommand,
    FixLatexCommand,
    GroupDiveCommand,
    IntegrateCommand,
    ReTutorCommand,
    StudentNoteCommand,
    TutorQuestionCommand,
)
from server.errors import ApiError
from server.tasking import JsonObject, TaskContext, TaskManager, TaskResult

from . import system as system_service
from .assets import normalize_asset_name, resolve_asset_dir, resolve_relative_file


def _normalize_asset_artifact_path(asset_name: str | None, artifact_path: str | Path | None) -> str | None:
    if artifact_path is None:
        return None

    raw_path = Path(artifact_path)
    if asset_name is None:
        return str(raw_path)

    try:
        asset_dir = resolve_asset_dir(asset_name)
        resolved = raw_path.resolve()
        return resolved.relative_to(asset_dir.resolve()).as_posix()
    except Exception:
        return str(raw_path)


def _workflow_callback(context: TaskContext, asset_name: str | None = None) -> Callable[[WorkflowEvent], None]:
    def _callback(event: WorkflowEvent) -> None:
        event_type = event.type
        message = event.message
        progress = event.progress
        artifact_path = event.artifact_path
        payload = event.payload
        if not isinstance(message, str) or not message:
            return
        if event_type == "progress":
            context.progress(message, progress)
        elif event_type == "artifact":
            if artifact_path is not None:
                context.artifact(
                    _normalize_asset_artifact_path(asset_name, artifact_path) or str(artifact_path),
                    message,
                    payload=payload if isinstance(payload, dict) else None,
                )
            else:
                context.log(message, payload=payload if isinstance(payload, dict) else None)
        elif event_type in {"queued", "started", "log"}:
            context.log(message, payload=payload if isinstance(payload, dict) else None)

    return _callback


def _cleanup_dir(path: Path | None) -> None:
    if path is None:
        return
    shutil.rmtree(path, ignore_errors=True)


def _resolve_pdf_path(asset_name: str) -> Path:
    normalized = normalize_asset_name(asset_name)
    resolve_asset_dir(normalized)
    pdf_path = get_asset_pdf_path(normalized)
    if not pdf_path.is_file():
        raise ApiError(404, "pdf_not_found", f"PDF not found for asset '{normalized}'.")
    return pdf_path


def _resolve_tutor_session_dir(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    tutor_session_dir = (
        resolve_asset_dir(asset_name)
        / "group_data"
        / str(group_idx)
        / "tutor_data"
        / str(tutor_idx)
    )
    if not tutor_session_dir.is_dir():
        raise ApiError(
            404,
            "tutor_session_not_found",
            f"Tutor session {group_idx}/{tutor_idx} not found for asset '{asset_name}'.",
        )
    return tutor_session_dir


def _store_manuscript_files(
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    manuscript_files: list[Path],
) -> list[Path]:
    tutor_session_dir = _resolve_tutor_session_dir(asset_name, group_idx, tutor_idx)

    for existing in tutor_session_dir.glob("manuscript_*.png"):
        existing.unlink(missing_ok=True)
    (tutor_session_dir / "manuscript.png").unlink(missing_ok=True)

    stored: list[Path] = []
    for index, source in enumerate(manuscript_files, start=1):
        target = tutor_session_dir / f"manuscript_{index}.png"
        shutil.copyfile(source, target)
        stored.append(target)
    return stored


def _build_asset_result(result: AssetInitResult, asset_name: str, message: str) -> TaskResult:
    payload: JsonObject = {
        "assetName": asset_name,
        "rawPdfPath": str(result.raw_pdf_path),
        "assetDir": str(result.asset_dir),
        "referenceFiles": [str(path) for path in result.reference_files],
    }
    return TaskResult(
        message=message,
        artifact_path=str(result.asset_dir),
        payload=payload,
    )


def submit_asset_init_task(
    manager: TaskManager,
    *,
    command: AssetInitCommand,
    cleanup_dir: Path | None = None,
) -> JsonObject:
    normalized = normalize_asset_name(command.asset_name)
    resolved_command = AssetInitCommand(
        asset_name=normalized,
        source_path=command.source_path,
        rendered_pdf_path=command.rendered_pdf_path,
        content_list_path=command.content_list_path,
    )

    def _runner(context: TaskContext) -> TaskResult:
        try:
            context.log(f"Initializing asset '{normalized}'.")
            result = orchestrator.asset_init(
                resolved_command,
                progress_callback=context.log,
                event_callback=_workflow_callback(context, normalized),
            )
            return _build_asset_result(result, normalized, f"Asset '{normalized}' initialized.")
        finally:
            _cleanup_dir(cleanup_dir)

    return manager.submit_task(
        kind="asset_init",
        title=f"Asset init: {normalized}",
        asset_name=normalized,
        runner=_runner,
    )


def submit_group_dive_task(manager: TaskManager, *, asset_name: str, group_idx: int) -> JsonObject:
    normalized = normalize_asset_name(asset_name)
    command = GroupDiveCommand(asset_name=normalized, group_idx=group_idx)

    def _runner(context: TaskContext) -> TaskResult:
        context.log(f"Running group dive for group {group_idx}.")
        output_path = orchestrator.group_dive_in(
            command,
            on_secondary_ready=lambda path: context.artifact(
                _normalize_asset_artifact_path(normalized, path) or str(path),
                f"Secondary group-dive output ready for group {group_idx}.",
            ),
            event_callback=_workflow_callback(context, normalized),
        )
        normalized_output_path = _normalize_asset_artifact_path(normalized, output_path)
        return TaskResult(
            message=f"Group dive for group {group_idx} completed.",
            artifact_path=normalized_output_path,
            payload={
                "groupIdx": group_idx,
                "markdownPath": normalized_output_path,
            },
        )

    return manager.submit_task(
        kind="group_dive",
        title=f"Group dive: group {group_idx}",
        asset_name=normalized,
        runner=_runner,
    )


def submit_ask_tutor_task(
    manager: TaskManager,
    *,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    question: str,
) -> JsonObject:
    normalized = normalize_asset_name(asset_name)
    app_config = system_service.get_app_config()
    command = TutorQuestionCommand(
        kind="ask_tutor",
        asset_name=normalized,
        group_idx=group_idx,
        tutor_idx=tutor_idx,
        question=question,
        reasoning_effort=app_config.tutorReasoningEffort,
        with_global_context=app_config.tutorWithGlobalContext,
    )

    def _runner(context: TaskContext) -> TaskResult:
        context.log(f"Running Ask Tutor for group {group_idx}, tutor {tutor_idx}.")
        output_path = orchestrator.ask_tutor(command, event_callback=_workflow_callback(context, normalized))
        return TaskResult(
            message="Ask Tutor completed.",
            artifact_path=_normalize_asset_artifact_path(normalized, output_path),
            payload={"groupIdx": group_idx, "tutorIdx": tutor_idx},
        )

    return manager.submit_task(
        kind="ask_tutor",
        title=f"Ask Tutor: group {group_idx}",
        asset_name=normalized,
        runner=_runner,
    )


def submit_re_tutor_task(
    manager: TaskManager,
    *,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    question: str,
) -> JsonObject:
    normalized = normalize_asset_name(asset_name)
    command = ReTutorCommand(
        asset_name=normalized,
        group_idx=group_idx,
        tutor_idx=tutor_idx,
        question=question,
    )

    def _runner(context: TaskContext) -> TaskResult:
        context.log(f"Running Re-tutor for group {group_idx}, tutor {tutor_idx}.")
        output_path = orchestrator.ask_re_tutor(command, event_callback=_workflow_callback(context, normalized))
        return TaskResult(
            message="Re-tutor completed.",
            artifact_path=_normalize_asset_artifact_path(normalized, output_path),
            payload={"groupIdx": group_idx, "tutorIdx": tutor_idx},
        )

    return manager.submit_task(
        kind="re_tutor",
        title=f"Re-tutor: group {group_idx}",
        asset_name=normalized,
        runner=_runner,
    )


def submit_integrate_task(
    manager: TaskManager,
    *,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
) -> JsonObject:
    normalized = normalize_asset_name(asset_name)
    command = IntegrateCommand(asset_name=normalized, group_idx=group_idx, tutor_idx=tutor_idx)

    def _runner(context: TaskContext) -> TaskResult:
        context.log(f"Running integration for group {group_idx}, tutor {tutor_idx}.")
        output_path = orchestrator.integrate(command, event_callback=_workflow_callback(context, normalized))
        return TaskResult(
            message="Integration completed.",
            artifact_path=_normalize_asset_artifact_path(normalized, output_path),
            payload={"groupIdx": group_idx, "tutorIdx": tutor_idx},
        )

    return manager.submit_task(
        kind="integrate",
        title=f"Integrate: group {group_idx}",
        asset_name=normalized,
        runner=_runner,
    )


def submit_bug_finder_task(
    manager: TaskManager,
    *,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    manuscript_files: list[Path] | None = None,
    cleanup_dir: Path | None = None,
) -> JsonObject:
    normalized = normalize_asset_name(asset_name)
    command = BugFinderCommand(
        asset_name=normalized,
        group_idx=group_idx,
        tutor_idx=tutor_idx,
        manuscript_files=tuple(manuscript_files or ()),
    )

    def _runner(context: TaskContext) -> TaskResult:
        try:
            context.log(f"Reviewing Feynman manuscript for group {group_idx}, tutor {tutor_idx}.")
            if command.manuscript_files:
                stored_files = _store_manuscript_files(normalized, group_idx, tutor_idx, list(command.manuscript_files))
                context.log(f"Stored {len(stored_files)} manuscript image(s).")
            output_path = orchestrator.bug_finder(command, event_callback=_workflow_callback(context, normalized))
            return TaskResult(
                message="Bug review completed.",
                artifact_path=_normalize_asset_artifact_path(normalized, output_path),
                payload={"groupIdx": group_idx, "tutorIdx": tutor_idx},
            )
        finally:
            _cleanup_dir(cleanup_dir)

    return manager.submit_task(
        kind="bug_finder",
        title=f"Bug Finder: group {group_idx}",
        asset_name=normalized,
        runner=_runner,
    )


def submit_student_note_task(
    manager: TaskManager,
    *,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
) -> JsonObject:
    normalized = normalize_asset_name(asset_name)
    command = StudentNoteCommand(asset_name=normalized, group_idx=group_idx, tutor_idx=tutor_idx)

    def _runner(context: TaskContext) -> TaskResult:
        context.log(f"Generating student note for group {group_idx}, tutor {tutor_idx}.")
        output_path = orchestrator.create_student_note(command, event_callback=_workflow_callback(context, normalized))
        return TaskResult(
            message="Student note completed.",
            artifact_path=_normalize_asset_artifact_path(normalized, output_path),
            payload={"groupIdx": group_idx, "tutorIdx": tutor_idx},
        )

    return manager.submit_task(
        kind="student_note",
        title=f"Student Note: group {group_idx}",
        asset_name=normalized,
        runner=_runner,
    )


def submit_fix_latex_task(
    manager: TaskManager,
    *,
    asset_name: str | None,
    markdown_path: str,
) -> JsonObject:
    normalized = normalize_asset_name(asset_name) if asset_name else None
    command = FixLatexCommand(asset_name=normalized, markdown_path=markdown_path)
    resolved_path = resolve_relative_file(normalized, command.markdown_path) if normalized else Path(command.markdown_path).resolve()
    if not resolved_path.is_file():
        raise ApiError(404, "markdown_not_found", f"Markdown not found: {markdown_path}")
    if resolved_path.suffix.lower() != ".md":
        raise ApiError(400, "invalid_markdown_path", "fix_latex only supports markdown files.")

    def _runner(context: TaskContext) -> TaskResult:
        context.log(f"Fixing LaTeX in {resolved_path.name}.")
        output_path = orchestrator.fix_latex(
            command,
            resolved_markdown_path=resolved_path,
            event_callback=_workflow_callback(context, normalized),
        )
        normalized_output_path = _normalize_asset_artifact_path(normalized, output_path)
        return TaskResult(
            message="LaTeX fix completed.",
            artifact_path=normalized_output_path,
            payload={"markdownPath": normalized_output_path or str(output_path)},
        )

    return manager.submit_task(
        kind="fix_latex",
        title=f"Fix LaTeX: {resolved_path.name}",
        asset_name=normalized,
        runner=_runner,
    )


def _compress_preview_payload(preview: CompressPreviewResult) -> JsonObject:
    image_bytes = preview.image_path.read_bytes()
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return {
        "previewImagePath": str(preview.image_path),
        "previewDataUrl": f"data:image/png;base64,{encoded}",
        "sizeBytes": preview.size_bytes,
        "width": preview.width,
        "height": preview.height,
    }


def submit_compress_preview_task(
    manager: TaskManager,
    *,
    asset_name: str,
    fraction_rect: tuple[float, float, float, float],
    ratio: int,
    compress_scale: float,
    draw_badge: bool,
    badge_position: str,
) -> JsonObject:
    normalized = normalize_asset_name(asset_name)
    command = CompressCommand(
        kind="compress_preview",
        asset_name=normalized,
        fraction_rect=fraction_rect,
        ratio=ratio,
        compress_scale=compress_scale,
        draw_badge=draw_badge,
        badge_position=badge_position,
    )
    source_pdf_path = _resolve_pdf_path(normalized)
    temp_output_dir = Path(tempfile.mkdtemp(prefix="exocortex_web_compress_preview_"))

    def _runner(context: TaskContext) -> TaskResult:
        try:
            context.log("Generating compression preview.")
            preview = render_compress_preview(
                source_pdf_path,
                command.fraction_rect,
                command.ratio,
                temp_output_dir,
                compress_scale=command.compress_scale,
                draw_badge=command.draw_badge,
                badge_position=command.badge_position,
            )
            payload = _compress_preview_payload(preview)
            return TaskResult(
                message="Compression preview ready.",
                artifact_path=str(preview.image_path),
                payload=payload,
            )
        except Exception as exc:
            raise ApiError(500, "compress_preview_failed", str(exc)) from exc
        finally:
            _cleanup_dir(temp_output_dir)

    return manager.submit_task(
        kind="compress_preview",
        title="Compress Preview",
        asset_name=normalized,
        runner=_runner,
    )


def submit_compress_execute_task(
    manager: TaskManager,
    *,
    asset_name: str,
    fraction_rect: tuple[float, float, float, float],
    ratio: int,
    compress_scale: float,
    draw_badge: bool,
    badge_position: str,
) -> JsonObject:
    normalized = normalize_asset_name(asset_name)
    command = CompressCommand(
        kind="compress_execute",
        asset_name=normalized,
        fraction_rect=fraction_rect,
        ratio=ratio,
        compress_scale=compress_scale,
        draw_badge=draw_badge,
        badge_position=badge_position,
    )
    source_pdf_path = _resolve_pdf_path(normalized)
    temp_output_dir = Path(tempfile.mkdtemp(prefix="exocortex_web_compress_execute_"))
    compressed_pdf_path = temp_output_dir / "compressed.pdf"

    def _runner(context: TaskContext) -> TaskResult:
        try:
            context.log(f"Compressing PDF for asset '{normalized}'.")
            output_path = compress_pdf_selection(
                source_pdf_path,
                command.fraction_rect,
                command.ratio,
                compressed_pdf_path,
                compress_scale=command.compress_scale,
                draw_badge=command.draw_badge,
                badge_position=command.badge_position,
            )
            context.artifact(output_path, "Compressed PDF ready.")
            result = orchestrator.asset_init(
                AssetInitCommand(asset_name=normalized, source_path=Path(output_path)),
                progress_callback=context.log,
                event_callback=_workflow_callback(context),
            )
            return _build_asset_result(result, normalized, f"Compressed asset '{normalized}' initialized.")
        except Exception as exc:
            raise ApiError(500, "compress_execute_failed", str(exc)) from exc
        finally:
            _cleanup_dir(temp_output_dir)

    return manager.submit_task(
        kind="compress_execute",
        title=f"Compress Execute: {normalized}",
        asset_name=normalized,
        runner=_runner,
    )


__all__ = [
    "submit_asset_init_task",
    "submit_ask_tutor_task",
    "submit_bug_finder_task",
    "submit_compress_execute_task",
    "submit_compress_preview_task",
    "submit_fix_latex_task",
    "submit_group_dive_task",
    "submit_integrate_task",
    "submit_re_tutor_task",
    "submit_student_note_task",
]
