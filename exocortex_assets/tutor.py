from __future__ import annotations

import re
import shutil
from pathlib import Path

from agent_manager import AgentJob, RunnerConfig, run_agent_job

from .constants import (
    BUG_FINDER_GEMINI_PROMPT,
    CODEX_MODEL,
    CODEX_REASONING_HIGH,
    GEMINI_MODEL,
    INTEGRATOR_CODEX_PROMPT,
    LATEX_FIXER_GEMINI_PROMPT,
    MANUSCRIPT_GEMINI_PROMPT,
    RE_TUTOR_GEMINI_PROMPT,
    TUTOR_GEMINI_PROMPT,
    relative_to_repo,
)
from .fs_utils import next_directory_index, next_markdown_index
from .markdown_utils import clean_markdown_file
from .references import collect_reference_files
from .storage import get_group_data_dir


def init_tutor(asset_name: str, group_idx: int, focus_markdown: str) -> Path:
    if not focus_markdown.strip():
        raise ValueError("Focus markdown is required.")

    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_data_dir = group_dir / "tutor_data"
    tutor_data_dir.mkdir(parents=True, exist_ok=True)
    tutor_idx = next_directory_index(tutor_data_dir)
    session_dir = tutor_data_dir / str(tutor_idx)
    while session_dir.exists():
        tutor_idx += 1
        session_dir = tutor_data_dir / str(tutor_idx)
    session_dir.mkdir(parents=True, exist_ok=False)

    focus_path = session_dir / "focus.md"
    focus_path.write_text(focus_markdown, encoding="utf-8", newline="\n")
    return focus_path


def _normalize_question(question: str) -> str:
    return question.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "").strip()


def _sorted_history_files(history_dir: Path) -> list[Path]:
    if not history_dir.is_dir():
        return []

    def _order_key(path: Path) -> tuple[int, str]:
        stem = path.stem
        try:
            return int(stem), stem
        except Exception:
            return 1_000_000, stem

    return sorted([path for path in history_dir.glob("*.md") if path.is_file()], key=_order_key)


def _append_history(input_path: Path, history_dir: Path) -> None:
    history_files = _sorted_history_files(history_dir)
    if not history_files:
        return
    with input_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n\n# 历史对话：\n")
        for history_path in history_files:
            try:
                history_text = history_path.read_text(encoding="utf-8")
            except Exception:  # pragma: no cover - defensive
                continue
            handle.write("\n\n")
            handle.write(history_text.rstrip())


def _find_focus(enhanced_content: str, focus_content: str) -> tuple[int, str]:
    match_start = -1
    match_text = ""
    for candidate in (focus_content, focus_content.rstrip("\n"), focus_content.strip()):
        if not candidate:
            continue
        match_start = enhanced_content.find(candidate)
        if match_start >= 0:
            match_text = candidate
            break
    if match_start < 0:
        raise ValueError("focus.md content not found in enhanced.md for insertion.")
    return match_start, match_text


def _ensure_block_after(content: str, insert_at: int, block: str) -> tuple[str, int]:
    if not block:
        return content, insert_at
    pos = content.find(block, insert_at)
    if pos >= 0:
        return content, pos + len(block)
    updated = content[:insert_at] + block + content[insert_at:]
    return updated, insert_at + len(block)


def ask_tutor(question: str, asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    normalized_question = _normalize_question(question)
    if not normalized_question:
        raise ValueError("Question is required.")

    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")
    focus_md = tutor_session_dir / "focus.md"
    if not focus_md.is_file():
        raise FileNotFoundError(f"tutor focus.md not found: {focus_md}")

    tutor_input_path = tutor_session_dir / "input.md"
    tutor_input_path.write_text(
        focus_md.read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )

    ask_history_dir = tutor_session_dir / "ask_history"
    if ask_history_dir.is_dir():
        _append_history(tutor_input_path, ask_history_dir)

    ask_history_dir.mkdir(parents=True, exist_ok=True)
    next_idx = next_markdown_index(ask_history_dir)
    output_name = f"{next_idx}.md"

    reference_files, reference_rename = collect_reference_files(
        asset_name,
        include_entire_content=True,
    )

    job = AgentJob(
        name="tutor",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=TUTOR_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message=f"{normalized_question}把讲解保存至 output/output.md",
            )
        ],
        input_files=[tutor_input_path],
        input_rename={tutor_input_path.name: "input.md"},
        reference_files=reference_files,
        reference_rename=reference_rename,
        deliver_dir=relative_to_repo(ask_history_dir),
        deliver_rename={"output.md": output_name},
        clean_markdown=True,
    )
    run_agent_job(job)

    moved_output = ask_history_dir / output_name
    if not moved_output.is_file():
        raise FileNotFoundError(f"tutor output not found at {moved_output}")

    answer = moved_output.read_text(encoding="utf-8")
    header = f"## 提问：\n\n{normalized_question}\n\n## 回答：\n\n"
    moved_output.write_text(header + answer.lstrip(), encoding="utf-8", newline="\n")
    return moved_output


def integrate(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")
    focus_md = tutor_session_dir / "focus.md"
    if not focus_md.is_file():
        raise FileNotFoundError(f"tutor focus.md not found: {focus_md}")

    integrator_input_path = tutor_session_dir / "integrator_input.md"
    integrator_input_path.write_text(
        focus_md.read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )

    ask_history_dir = tutor_session_dir / "ask_history"
    if ask_history_dir.is_dir():
        _append_history(integrator_input_path, ask_history_dir)

    existing_input = integrator_input_path.read_text(encoding="utf-8")
    integrator_input_path.write_text(
        f"# 原始教学内容\n\n{existing_input}",
        encoding="utf-8",
        newline="\n",
    )

    reference_files, reference_rename = collect_reference_files(
        asset_name,
        reference_filenames=("formula.md", "concept.md"),
    )

    note_path = tutor_session_dir / "note.md"

    job = AgentJob(
        name="integrator",
        runners=[
            RunnerConfig(
                runner="codex",
                prompt_path=INTEGRATOR_CODEX_PROMPT,
                model=CODEX_MODEL,
                reasoning_effort=CODEX_REASONING_HIGH,
                new_console=True,
            )
        ],
        input_files=[integrator_input_path],
        input_rename={integrator_input_path.name: "input.md"},
        reference_files=reference_files,
        reference_rename=reference_rename,
        deliver_dir=relative_to_repo(tutor_session_dir),
        deliver_rename={"output.md": "note.md"},
        clean_markdown=True,
    )
    run_agent_job(job)

    if not note_path.is_file():
        raise FileNotFoundError(f"integrator output not found at {note_path}")

    note_content = note_path.read_text(encoding="utf-8").lstrip("\ufeff")
    note_lines = note_content.splitlines(keepends=True)
    summary_line = ""
    summary_index = None
    for idx, line in enumerate(note_lines):
        if not line.strip():
            continue
        summary_line = re.sub(r"^[#\s]+", "", line).strip()
        summary_index = idx
        if summary_line:
            break
    if not summary_line:
        summary_line = "笔记标题"
    if summary_index is not None:
        del note_lines[summary_index]
    note_body = "".join(note_lines)
    note_wrapped = (
        '\n\n<details class="note"> \n'
        f"<summary>{summary_line}</summary> \n"
        '<div markdown="1">\n\n'
        f"{note_body}"
        "\n\n</div> \n</details>\n\n"
    )
    note_path.write_text(note_wrapped, encoding="utf-8", newline="\n")

    img_explainer_dir = group_dir / "img_explainer_data"
    enhanced_md = img_explainer_dir / "enhanced.md"
    if not enhanced_md.is_file():
        raise FileNotFoundError(f"enhanced.md not found at {enhanced_md}")

    enhanced_content = enhanced_md.read_text(encoding="utf-8")
    focus_content = focus_md.read_text(encoding="utf-8")
    if not focus_content.strip():
        raise ValueError(f"focus.md is empty: {focus_md}")

    match_start, match_text = _find_focus(enhanced_content, focus_content)
    insert_at = match_start + len(match_text)
    updated_enhanced = enhanced_content[:insert_at] + note_wrapped + enhanced_content[insert_at:]
    enhanced_md.write_text(updated_enhanced, encoding="utf-8", newline="\n")
    return enhanced_md


_MANUSCRIPT_IMAGE_RE = re.compile(r"^manuscript_(\d+)\.png$", re.IGNORECASE)


def list_tutor_manuscript_images(tutor_session_dir: Path) -> list[Path]:
    indexed: list[tuple[int, Path]] = []
    if tutor_session_dir.is_dir():
        for entry in tutor_session_dir.iterdir():
            if not entry.is_file():
                continue
            match = _MANUSCRIPT_IMAGE_RE.match(entry.name)
            if not match:
                continue
            try:
                idx = int(match.group(1))
            except (TypeError, ValueError):
                continue
            indexed.append((idx, entry))

    if indexed:
        indexed.sort(key=lambda item: item[0])
        return [path for _, path in indexed]

    single = tutor_session_dir / "manuscript.png"
    if single.is_file():
        return [single]

    legacy = tutor_session_dir / "student.png"
    if legacy.is_file():
        return [legacy]

    return []


def bug_finder(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")

    manuscript_images = list_tutor_manuscript_images(tutor_session_dir)
    if not manuscript_images:
        raise FileNotFoundError(
            f"No manuscript images found in {tutor_session_dir} (expected manuscript_*.png)"
        )

    note_path = tutor_session_dir / "note.md"
    if not note_path.is_file():
        raise FileNotFoundError(f"note.md not found: {note_path}")

    bugs_path = tutor_session_dir / "bugs.md"

    manuscript_refs = " ".join(
        f"@input/manuscript_{idx}.png" for idx in range(1, len(manuscript_images) + 1)
    )
    extra_message = f"{manuscript_refs} 是手稿笔记，开始"
    input_rename = {
        image.name: f"manuscript_{idx}.png" for idx, image in enumerate(manuscript_images, start=1)
    }

    job = AgentJob(
        name="bug_finder",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=BUG_FINDER_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message=extra_message,
            )
        ],
        input_files=manuscript_images,
        input_rename=input_rename,
        reference_files=[note_path],
        reference_rename={note_path.name: "original.md"},
        deliver_dir=relative_to_repo(tutor_session_dir),
        deliver_rename={"bugs.md": "bugs.md"},
        clean_markdown=True,
    )
    run_agent_job(job)

    if not bugs_path.is_file():
        raise FileNotFoundError(f"bug_finder output not found at {bugs_path}")
    return bugs_path


def ask_re_tutor(question: str, asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    normalized_question = _normalize_question(question)
    if not normalized_question:
        raise ValueError("Question is required.")

    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")

    manuscript_images = list_tutor_manuscript_images(tutor_session_dir)
    if not manuscript_images:
        raise FileNotFoundError(
            f"No manuscript images found in {tutor_session_dir} (expected manuscript_*.png)"
        )

    note_path = tutor_session_dir / "note.md"
    if not note_path.is_file():
        raise FileNotFoundError(f"note.md not found: {note_path}")

    bugs_path = tutor_session_dir / "bugs.md"
    if not bugs_path.is_file():
        raise FileNotFoundError(f"bugs.md not found: {bugs_path}")

    input_rename = {
        image.name: f"manuscript_{idx}.png" for idx, image in enumerate(manuscript_images, start=1)
    }
    input_rename[bugs_path.name] = "bugs.md"

    re_tutor_output_name = "re_tutor_output.md"
    job = AgentJob(
        name="re_tutor",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=RE_TUTOR_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message=f"{normalized_question}把解答保存至 output/output.md",
            )
        ],
        input_files=[*manuscript_images, bugs_path],
        input_rename=input_rename,
        reference_files=[note_path],
        reference_rename={note_path.name: "original.md"},
        deliver_dir=relative_to_repo(tutor_session_dir),
        deliver_rename={"output.md": re_tutor_output_name},
        clean_markdown=True,
    )
    run_agent_job(job)

    answer_path = tutor_session_dir / re_tutor_output_name
    if not answer_path.is_file():
        raise FileNotFoundError(f"re_tutor output not found at {answer_path}")

    bugs_text = bugs_path.read_text(encoding="utf-8-sig").lstrip("\ufeff").rstrip()
    answer_text = answer_path.read_text(encoding="utf-8-sig").lstrip("\ufeff").lstrip()

    separator = "\n\n" if bugs_text else ""
    appended = (
        f"{bugs_text}{separator}"
        f"## 提问\n\n{normalized_question}\n\n"
        f"## 回答\n\n{answer_text}\n"
    )
    bugs_path.write_text(appended, encoding="utf-8", newline="\n")
    clean_markdown_file(bugs_path)
    return bugs_path


def insert_feynman_original_image(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")

    manuscript_images = list_tutor_manuscript_images(tutor_session_dir)
    if not manuscript_images:
        raise FileNotFoundError(
            f"No manuscript images found in {tutor_session_dir} (expected manuscript_*.png)"
        )

    focus_md = tutor_session_dir / "focus.md"
    if not focus_md.is_file():
        raise FileNotFoundError(f"tutor focus.md not found: {focus_md}")

    img_explainer_dir = group_dir / "img_explainer_data"
    enhanced_md = img_explainer_dir / "enhanced.md"
    if not enhanced_md.is_file():
        raise FileNotFoundError(f"enhanced.md not found at {enhanced_md}")

    target_names: list[str] = []
    for idx, source in enumerate(manuscript_images, start=1):
        target_name = (
            f"manuscript_{tutor_idx}.png" if idx == 1 else f"manuscript_{tutor_idx}_{idx}.png"
        )
        target_image = img_explainer_dir / target_name
        target_image.unlink(missing_ok=True)
        shutil.copy2(source, target_image)
        target_names.append(target_name)

    image_markdown = "\n\n".join(f"![你的推导](img_explainer_data/{name})" for name in target_names)
    original_block = (
        "\n\n<details class=\"note\">\n"
        "<summary>原图</summary> \n"
        "<div markdown=\"1\">\n\n"
        f"{image_markdown}\n\n\n"
        "</div>\n"
        "</details>\n\n"
    )

    enhanced_content = enhanced_md.read_text(encoding="utf-8")

    focus_content = focus_md.read_text(encoding="utf-8")
    if not focus_content.strip():
        raise ValueError(f"focus.md is empty: {focus_md}")

    match_start, match_text = _find_focus(enhanced_content, focus_content)
    insert_at = match_start + len(match_text)

    note_path = tutor_session_dir / "note.md"
    note_wrapped = ""
    if note_path.is_file():
        try:
            note_wrapped = note_path.read_text(encoding="utf-8").lstrip("\ufeff")
        except Exception:  # pragma: no cover - defensive
            note_wrapped = ""

    enhanced_content, insert_at = _ensure_block_after(enhanced_content, insert_at, note_wrapped)
    updated_enhanced = enhanced_content[:insert_at] + original_block + enhanced_content[insert_at:]
    enhanced_md.write_text(updated_enhanced, encoding="utf-8", newline="\n")
    return enhanced_md


def create_student_note(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")

    manuscript_images = list_tutor_manuscript_images(tutor_session_dir)
    if not manuscript_images:
        raise FileNotFoundError(
            f"No manuscript images found in {tutor_session_dir} (expected manuscript_*.png)"
        )

    focus_md = tutor_session_dir / "focus.md"
    if not focus_md.is_file():
        raise FileNotFoundError(f"tutor focus.md not found: {focus_md}")

    img_explainer_dir = group_dir / "img_explainer_data"
    enhanced_md = img_explainer_dir / "enhanced.md"
    if not enhanced_md.is_file():
        raise FileNotFoundError(f"enhanced.md not found at {enhanced_md}")

    note_student_path = tutor_session_dir / "note_student.md"

    job = AgentJob(
        name="manuscript",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=MANUSCRIPT_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message=(
                    " ".join(
                        f"@input/manuscript_{idx}.png"
                        for idx in range(1, len(manuscript_images) + 1)
                    )
                    + " 是手稿笔记，开始"
                ),
            )
        ],
        input_files=manuscript_images,
        input_rename={
            image.name: f"manuscript_{idx}.png"
            for idx, image in enumerate(manuscript_images, start=1)
        },
        deliver_dir=relative_to_repo(tutor_session_dir),
        deliver_rename={"output.md": "note_student.md"},
        clean_markdown=True,
    )
    run_agent_job(job)

    if not note_student_path.is_file():
        raise FileNotFoundError(f"manuscript output not found at {note_student_path}")

    raw_note_student = note_student_path.read_text(encoding="utf-8").lstrip("\ufeff")
    note_student_wrapped = (
        '\n\n<details class="note"> \n'
        "<summary>你的推导</summary>\n"
        '<div markdown="1">\n\n'
        f"{raw_note_student}"
        "\n\n</div> \n</details>\n\n"
    )
    note_student_path.write_text(note_student_wrapped, encoding="utf-8", newline="\n")

    enhanced_content = enhanced_md.read_text(encoding="utf-8")

    focus_content = focus_md.read_text(encoding="utf-8")
    if not focus_content.strip():
        raise ValueError(f"focus.md is empty: {focus_md}")

    match_start, match_text = _find_focus(enhanced_content, focus_content)
    insert_at = match_start + len(match_text)

    note_path = tutor_session_dir / "note.md"
    note_wrapped = ""
    if note_path.is_file():
        try:
            note_wrapped = note_path.read_text(encoding="utf-8").lstrip("\ufeff")
        except Exception:  # pragma: no cover - defensive
            note_wrapped = ""
    enhanced_content, insert_at = _ensure_block_after(enhanced_content, insert_at, note_wrapped)

    target_names = [
        f"manuscript_{tutor_idx}.png" if idx == 1 else f"manuscript_{tutor_idx}_{idx}.png"
        for idx in range(1, len(manuscript_images) + 1)
    ]

    image_markdown = "\n\n".join(f"![你的推导](img_explainer_data/{name})" for name in target_names)
    original_block = (
        "\n\n<details class=\"note\">\n"
        "<summary>原图</summary> \n"
        "<div markdown=\"1\">\n\n"
        f"{image_markdown}\n\n\n"
        "</div>\n"
        "</details>\n\n"
    )
    legacy_image_markdown = "\n\n".join(
        f"![你的推导](./img_explainer_data/{name})" for name in target_names
    )
    legacy_original_block = (
        "\n\n<details class=\"note\">\n"
        "<summary>原图</summary> \n"
        "<div markdown=\"1\">\n\n"
        f"{legacy_image_markdown}\n\n\n"
        "</div>\n"
        "</details>\n\n"
    )

    def _find_last_end(content: str, block: str, start: int) -> int | None:
        pos = content.find(block, start)
        if pos < 0:
            return None
        last_end = pos + len(block)
        while True:
            next_pos = content.find(block, last_end)
            if next_pos < 0:
                return last_end
            last_end = next_pos + len(block)

    for block in (original_block, legacy_original_block):
        end_pos = _find_last_end(enhanced_content, block, insert_at)
        if end_pos is not None:
            insert_at = max(insert_at, end_pos)

    updated_enhanced = enhanced_content[:insert_at] + note_student_wrapped + enhanced_content[insert_at:]
    enhanced_md.write_text(updated_enhanced, encoding="utf-8", newline="\n")
    return enhanced_md


def fix_latex(markdown_path: str | Path) -> Path:
    path = Path(markdown_path)
    if not path.is_file():
        raise FileNotFoundError(f"Markdown not found: {path}")
    if path.suffix.lower() != ".md":
        raise ValueError(f"fix_latex only supports markdown files: {path}")

    job = AgentJob(
        name="latex_fixer",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=LATEX_FIXER_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message="Fix latex in @output/output.md and save to output/output.md.",
            )
        ],
        output_seed_files=[path],
        output_rename={path.name: "output.md"},
        deliver_dir=path.parent,
        deliver_rename={"output.md": path.name},
        clean_markdown=True,
    )
    run_agent_job(job)

    if not path.is_file():
        raise FileNotFoundError(f"Latex fixer output not found at {path}")
    return path

