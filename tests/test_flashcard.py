from __future__ import annotations

import json
import sqlite3
import time
import zipfile
from pathlib import Path

import pytest

import agent_manager
import assets_manager
from exocortex_core.markdown_viewer import AnkiMarkdownViewerAssets
from server.errors import ApiError
from server.services import assets as assets_service
from server.services import system as system_service
from server.services import workflows as workflow_service
from server.tasking.manager import TaskManager


def _wait_for_terminal_task(manager: TaskManager, task_id: str, timeout_seconds: float = 3.0) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        detail = manager.get_task(task_id)
        if detail["status"] in {"completed", "failed"}:
            return detail
        time.sleep(0.01)
    raise AssertionError(f"task {task_id} did not finish within {timeout_seconds} seconds")


def _create_group_fixture(
    root: Path,
    *,
    asset_name: str = "demo",
    group_idx: int = 1,
    include_content: bool = True,
    ask_history: dict[tuple[int, str], str] | None = None,
) -> Path:
    group_dir = root / asset_name / "group_data" / str(group_idx)
    (group_dir / "img_explainer_data").mkdir(parents=True, exist_ok=True)
    if include_content:
        (group_dir / "content.md").write_text(
            "# Content\n\nCore content",
            encoding="utf-8",
            newline="\n",
        )

    if ask_history == {}:
        (group_dir / "tutor_data" / "1" / "ask_history").mkdir(parents=True, exist_ok=True)

    for (tutor_idx, filename), content in (ask_history or {}).items():
        ask_history_dir = group_dir / "tutor_data" / str(tutor_idx) / "ask_history"
        ask_history_dir.mkdir(parents=True, exist_ok=True)
        (ask_history_dir / filename).write_text(content, encoding="utf-8", newline="\n")

    return group_dir


def _create_mock_anki_assets(tmp_path: Path) -> AnkiMarkdownViewerAssets:
    media_dir = tmp_path / "anki-media"
    media_dir.mkdir(parents=True, exist_ok=True)
    media_files: list[Path] = []
    for relative_path in ("katex.min.js", "auto-render.min.js", "copy-tex.min.js"):
        path = media_dir / relative_path
        path.write_text("// mock", encoding="utf-8", newline="\n")
        media_files.append(path)
    return AnkiMarkdownViewerAssets(css=".markdown-rendered { color: #111; }", scripts_html="", media_files=tuple(media_files))


def _read_apkg_metadata(apkg_path: Path) -> tuple[list[str], list[str], dict[str, object]]:
    extracted_db = apkg_path.with_suffix(".anki2")
    with zipfile.ZipFile(apkg_path) as archive:
        with archive.open("collection.anki2") as handle:
            extracted_db.write_bytes(handle.read())

    connection = sqlite3.connect(extracted_db)
    try:
        cursor = connection.cursor()
        notes = [row[0] for row in cursor.execute("select guid from notes order by guid").fetchall()]
        fields = [row[0] for row in cursor.execute("select flds from notes order by guid").fetchall()]
        decks_raw = cursor.execute("select decks from col").fetchone()[0]
    finally:
        connection.close()
        extracted_db.unlink(missing_ok=True)

    return notes, fields, json.loads(decks_raw)


def test_extract_flashcard_sections_parses_question_and_answer_blocks() -> None:
    front, back = assets_manager._extract_flashcard_sections(
        "question:\nFront body\n\n- bullet\nanswer:\nBack body\n\nMore detail.\n"
    )

    assert front == "Front body\n\n- bullet"
    assert back == "Back body\n\nMore detail."


def test_extract_flashcard_sections_falls_back_when_a_side_is_empty() -> None:
    markdown = "question:\n\nanswer:\nBack only\n"

    front, back = assets_manager._extract_flashcard_sections(markdown)

    assert front == markdown.strip()
    assert back == markdown.strip()


def test_flashcard_collects_ask_history_in_numeric_order_and_appends_outputs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    group_dir = _create_group_fixture(
        tmp_path,
        ask_history={
            (1, "2.md"): "T1-H2",
            (1, "10.md"): "T1-H10",
            (1, "appendix.md"): "T1-APP",
            (2, "1.md"): "T2-H1",
            (10, "3.md"): "T10-H3",
        },
    )
    existing_flashcard_dir = group_dir / "flashcard" / "md"
    stale_path = existing_flashcard_dir / "stale.md"
    nested_existing = existing_flashcard_dir / "nested" / "card-2.txt"
    stale_path.parent.mkdir(parents=True, exist_ok=True)
    nested_existing.parent.mkdir(parents=True, exist_ok=True)
    stale_path.write_text("stale", encoding="utf-8", newline="\n")
    nested_existing.write_text("old raw", encoding="utf-8", newline="\n")

    monkeypatch.setattr(assets_manager, "ASSETS_ROOT", tmp_path)
    captured: dict[str, object] = {}

    def fake_run_agent_job(job, *, event_callback=None):
        qa_reference = next(path for path in job.reference_files if path.name == "QA.md")
        captured["reference_text"] = qa_reference.read_text(encoding="utf-8")
        captured["reference_rename"] = dict(job.reference_rename)
        workspace = tmp_path / "workspace"
        output_dir = workspace / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "card-1.md").write_text("question:\nA\nanswer:\nB\n", encoding="utf-8", newline="\n")
        (output_dir / "card-2.txt").write_text("raw", encoding="utf-8", newline="\n")
        nested_dir = output_dir / "nested"
        nested_dir.mkdir(parents=True, exist_ok=True)
        (nested_dir / "card-2.txt").write_text("new raw", encoding="utf-8", newline="\n")
        agent_manager._deliver_outputs(job, workspace)

    monkeypatch.setattr(assets_manager, "run_agent_job", fake_run_agent_job)

    output_dir = assets_manager.flashcard("demo", 1)

    assert output_dir == group_dir / "flashcard" / "md"
    assert stale_path.is_file()
    assert (output_dir / "card-1.md").is_file()
    assert (output_dir / "card-2.txt").is_file()
    assert (output_dir / "nested" / "card-2.txt").read_text(encoding="utf-8") == "old raw"
    assert (output_dir / "nested" / "card-2_1.txt").read_text(encoding="utf-8") == "new raw"
    assert captured["reference_text"] == "T1-H2\n\nT1-H10\n\nT1-APP\n\nT2-H1\n\nT10-H3\n"
    reference_targets = set(captured["reference_rename"].values())
    assert "flashcards/stale.md" in reference_targets
    assert "flashcards/nested/card-2.txt" in reference_targets


def test_flashcard_exports_html_and_apkg_with_cleanup_and_stable_ids(
    tmp_path: Path,
    monkeypatch,
) -> None:
    group_dir = _create_group_fixture(tmp_path, ask_history={(1, "1.md"): "Q1"})
    flashcard_dir = group_dir / "flashcard" / "md"
    html_dir = group_dir / "flashcard" / "html"
    apkg_dir = group_dir / "flashcard" / "apkg"
    (group_dir / "group.alias").write_text("Shared Deck", encoding="utf-8", newline="\n")

    stale_html = html_dir / "stale.html"
    stale_apkg = apkg_dir / "stale.apkg"
    stale_html.parent.mkdir(parents=True, exist_ok=True)
    stale_apkg.parent.mkdir(parents=True, exist_ok=True)
    stale_html.write_text("old", encoding="utf-8", newline="\n")
    stale_apkg.write_text("old", encoding="utf-8", newline="\n")

    monkeypatch.setattr(assets_manager, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(assets_manager, "anki_markdown_viewer_assets", lambda: _create_mock_anki_assets(tmp_path))

    def fake_run_agent_job(job, *, event_callback=None):
        workspace = tmp_path / "workspace-export"
        output_dir = workspace / "output"
        (output_dir / "nested").mkdir(parents=True, exist_ok=True)
        (output_dir / "good.md").write_text(
            "question:\n## Front side\n\n$E=mc^2$\nanswer:\n### Back side\n\nDetailed answer.",
            encoding="utf-8",
            newline="\n",
        )
        (output_dir / "nested" / "bad.md").write_text(
            "# Missing markers\n\nFallback card body.",
            encoding="utf-8",
            newline="\n",
        )
        agent_manager._deliver_outputs(job, workspace)

    monkeypatch.setattr(assets_manager, "run_agent_job", fake_run_agent_job)

    output_dir = assets_manager.flashcard("demo", 1)

    assert output_dir == flashcard_dir
    assert not stale_html.exists()
    assert not stale_apkg.exists()

    good_front_html = html_dir / "good.front.html"
    good_back_html = html_dir / "good.back.html"
    bad_front_html = html_dir / "nested" / "bad.front.html"
    bad_back_html = html_dir / "nested" / "bad.back.html"
    apkg_path = apkg_dir / "deck.apkg"

    assert good_front_html.is_file()
    assert good_back_html.is_file()
    assert bad_front_html.is_file()
    assert bad_back_html.is_file()
    assert apkg_path.is_file()

    assert "Front side" in good_front_html.read_text(encoding="utf-8")
    assert "Back side" in good_back_html.read_text(encoding="utf-8")
    bad_front_text = bad_front_html.read_text(encoding="utf-8")
    bad_back_text = bad_back_html.read_text(encoding="utf-8")
    assert "Missing markers" in bad_front_text
    assert "Fallback card body." in bad_back_text

    note_guids, note_fields, decks = _read_apkg_metadata(apkg_path)
    assert note_guids == sorted(
        [
            assets_manager.genanki.guid_for("exocortex|anki-note|v1", "demo", "group_data/1/flashcard/md/good.md"),
            assets_manager.genanki.guid_for("exocortex|anki-note|v1", "demo", "group_data/1/flashcard/md/nested/bad.md"),
        ]
    )
    assert any("group_data/1/flashcard/md/good.md" in field_value for field_value in note_fields)
    assert any("group_data/1/flashcard/md/nested/bad.md" in field_value for field_value in note_fields)
    assert any(deck["name"] == "demo::Shared Deck" for deck in decks.values())
    expected_deck_id = str(assets_manager._stable_anki_id("exocortex|anki-deck|v1|demo|Shared Deck"))
    assert expected_deck_id in decks


def test_flashcard_requires_group_content_markdown(tmp_path: Path, monkeypatch) -> None:
    _create_group_fixture(tmp_path, include_content=False, ask_history={(1, "1.md"): "Q"})
    monkeypatch.setattr(assets_manager, "ASSETS_ROOT", tmp_path)

    with pytest.raises(FileNotFoundError, match="content.md"):
        assets_manager.flashcard("demo", 1)


@pytest.mark.parametrize("ask_history", [None, {}], ids=["missing-tutor-data", "empty-ask-history"])
def test_flashcard_allows_missing_qa_history_and_writes_placeholder(
    tmp_path: Path,
    monkeypatch,
    ask_history: dict[tuple[int, str], str] | None,
) -> None:
    _create_group_fixture(tmp_path, ask_history=ask_history)
    monkeypatch.setattr(assets_manager, "ASSETS_ROOT", tmp_path)

    captured: dict[str, str] = {}

    def fake_run_agent_job(job, *, event_callback=None):
        qa_reference = next(path for path in job.reference_files if path.name == "QA.md")
        captured["reference_text"] = qa_reference.read_text(encoding="utf-8")
        workspace = tmp_path / "workspace-no-qa"
        output_dir = workspace / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "card-1.md").write_text("question:\nA\nanswer:\nB\n", encoding="utf-8", newline="\n")
        agent_manager._deliver_outputs(job, workspace)

    monkeypatch.setattr(assets_manager, "run_agent_job", fake_run_agent_job)

    output_dir = assets_manager.flashcard("demo", 1)

    assert output_dir == tmp_path / "demo" / "group_data" / "1" / "flashcard" / "md"
    assert captured["reference_text"] == "there is no QA record\n"


def test_flashcard_requires_agent_outputs(tmp_path: Path, monkeypatch) -> None:
    _create_group_fixture(tmp_path, ask_history={(1, "1.md"): "Q"})
    monkeypatch.setattr(assets_manager, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(assets_manager, "run_agent_job", lambda job, *, event_callback=None: None)

    with pytest.raises(FileNotFoundError, match="flashcard output not found"):
        assets_manager.flashcard("demo", 1)


def test_submit_flashcard_task_returns_relative_flashcard_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    asset_dir = tmp_path / "demo"
    output_dir = asset_dir / "group_data" / "1" / "flashcard" / "md"
    output_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(assets_manager, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(assets_service, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(workflow_service.orchestrator, "flashcard", lambda command, *, event_callback=None: output_dir)

    manager = TaskManager(max_workers=1, event_buffer_size=16)
    try:
        summary = workflow_service.submit_flashcard_task(manager, asset_name="demo", group_idx=1)
        detail = _wait_for_terminal_task(manager, summary["id"])
    finally:
        manager.close()

    assert detail["status"] == "completed"
    assert detail["result"]["artifactPath"] == "group_data/1/flashcard/md"
    assert detail["result"]["payload"] == {
        "groupIdx": 1,
        "flashcardDir": "group_data/1/flashcard/md",
    }


def test_submit_flashcard_task_rejects_duplicate_active_group(
    tmp_path: Path,
    monkeypatch,
) -> None:
    asset_dir = tmp_path / "demo"
    asset_dir.mkdir(parents=True, exist_ok=True)
    started = False

    def fake_flashcard(command, *, event_callback=None):
        nonlocal started
        started = True
        time.sleep(0.2)
        return asset_dir / "group_data" / "1" / "flashcard" / "md"

    monkeypatch.setattr(assets_manager, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(assets_service, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(workflow_service.orchestrator, "flashcard", fake_flashcard)

    manager = TaskManager(max_workers=1, event_buffer_size=16)
    try:
        workflow_service.submit_flashcard_task(manager, asset_name="demo", group_idx=1)
        deadline = time.monotonic() + 1.0
        while not started and time.monotonic() < deadline:
            time.sleep(0.01)

        with pytest.raises(ApiError) as exc_info:
            workflow_service.submit_flashcard_task(manager, asset_name="demo", group_idx=1)
    finally:
        manager.close()

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "task_already_running"


def test_reveal_asset_path_is_noop_for_missing_flashcard_apkg_directory(tmp_path: Path, monkeypatch) -> None:
    asset_dir = tmp_path / "demo"
    asset_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        system_service,
        "resolve_relative_path",
        lambda asset_name, raw_path, must_exist=False: asset_dir / Path(raw_path),
    )

    assert system_service.reveal_asset_path("demo", "group_data/1/flashcard/apkg") is None


def test_reveal_asset_path_opens_existing_flashcard_apkg_directory(tmp_path: Path, monkeypatch) -> None:
    asset_dir = tmp_path / "demo"
    target_dir = asset_dir / "group_data" / "1" / "flashcard" / "apkg"
    target_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        system_service,
        "resolve_relative_path",
        lambda asset_name, raw_path, must_exist=False: asset_dir / Path(raw_path),
    )
    captured: list[tuple[Path, bool]] = []
    monkeypatch.setattr(system_service, "_reveal_path", lambda path, *, select_file: captured.append((path, select_file)) or path)

    result = system_service.reveal_asset_path("demo", "group_data/1/flashcard/apkg")

    assert result == target_dir
    assert captured == [(target_dir, False)]
