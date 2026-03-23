from __future__ import annotations

from pathlib import Path

import assets_manager


def _create_tutor_fixture(
    root: Path,
    *,
    asset_name: str = "demo",
    group_idx: int = 1,
    tutor_idx: int = 2,
    focus_text: str = "# Focus\n\nLine A\nLine B",
    history: dict[str, str] | None = None,
) -> Path:
    tutor_dir = root / asset_name / "group_data" / str(group_idx) / "tutor_data" / str(tutor_idx)
    tutor_dir.mkdir(parents=True, exist_ok=True)
    (tutor_dir / "focus.md").write_text(focus_text, encoding="utf-8", newline="\n")
    ask_history_dir = tutor_dir / "ask_history"
    ask_history_dir.mkdir(parents=True, exist_ok=True)
    for name, content in (history or {}).items():
        (ask_history_dir / name).write_text(content, encoding="utf-8", newline="\n")
    return tutor_dir


def test_ask_tutor_uses_configured_reasoning_effort_for_global_context(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tutor_dir = _create_tutor_fixture(tmp_path)
    monkeypatch.setattr(assets_manager, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(assets_manager, "_collect_reference_files", lambda *args, **kwargs: ([], {}))

    captured: dict[str, object] = {}

    def fake_run_agent_job(job, *, event_callback=None):
        captured["reasoning_effort"] = job.runners[0].reasoning_effort
        deliver_dir = Path(job.deliver_dir)
        deliver_dir.mkdir(parents=True, exist_ok=True)
        (deliver_dir / "1.md").write_text("Tutor body", encoding="utf-8", newline="\n")

    monkeypatch.setattr(assets_manager, "run_agent_job", fake_run_agent_job)

    output_path = assets_manager.ask_tutor(
        "Why is this stable?",
        "demo",
        1,
        2,
        reasoning_effort="xhigh",
        with_global_context=True,
    )

    assert captured["reasoning_effort"] == "xhigh"
    assert output_path == tutor_dir / "ask_history" / "1.md"
    assert "Why is this stable?" in output_path.read_text(encoding="utf-8")


def test_ask_tutor_without_global_context_flattens_prompt_and_archives_reply(
    tmp_path: Path,
    monkeypatch,
) -> None:
    tutor_dir = _create_tutor_fixture(
        tmp_path,
        focus_text="# Focus\n\nAlpha\nBeta",
        history={"1.md": "## Q\n\nOld question\n\n## A\n\nOld answer"},
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(assets_manager, "ASSETS_ROOT", tmp_path)
    monkeypatch.setattr(assets_manager, "create_workspace", lambda: workspace)

    captured: dict[str, object] = {}

    def fake_run_codex_capture_last_message(
        message: str,
        workdir: Path,
        *,
        output_last_message_path: Path,
        model: str,
        model_reasoning_effort: str,
        new_console: bool,
    ) -> str:
        captured["prompt"] = message
        captured["workdir"] = workdir
        captured["output_last_message_path"] = output_last_message_path
        captured["reasoning_effort"] = model_reasoning_effort
        return "Generated answer"

    monkeypatch.setattr(assets_manager, "run_codex_capture_last_message", fake_run_codex_capture_last_message)

    output_path = assets_manager.ask_tutor(
        "Why\nis this\nflat?",
        "demo",
        1,
        2,
        reasoning_effort="low",
        with_global_context=False,
    )

    tutor_input_path = tutor_dir / "input.md"
    expected_prompt = (
        assets_manager._flatten_prompt_text(tutor_input_path.read_text(encoding="utf-8"))
        + assets_manager._flatten_prompt_text("Why\nis this\nflat?")
    )

    assert captured["prompt"] == expected_prompt
    assert "\n" not in captured["prompt"]
    assert captured["workdir"] == workspace
    assert captured["output_last_message_path"] == workspace / "last_message.md"
    assert captured["reasoning_effort"] == "low"
    assert output_path == tutor_dir / "ask_history" / "2.md"
    saved = output_path.read_text(encoding="utf-8")
    assert "Generated answer" in saved
    assert assets_manager._flatten_prompt_text("Why\nis this\nflat?") in saved
