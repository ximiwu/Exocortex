from __future__ import annotations

import subprocess

import agent_manager


def test_new_console_requested_only_in_dev_runtime(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    monkeypatch.setattr(agent_manager.shutil, "which", lambda name: "codex.exe")
    monkeypatch.setattr(agent_manager, "is_dev_runtime", lambda: True)
    monkeypatch.setattr(subprocess, "CREATE_NEW_CONSOLE", 64, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 128, raising=False)

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["creationflags"] = kwargs.get("creationflags")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(agent_manager.subprocess, "run", fake_run)

    result = agent_manager.run_codex("Proceed.", tmp_path, new_console=True)

    assert result.returncode == 0
    assert captured["creationflags"] == 64


def test_new_console_suppressed_outside_dev_runtime(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    monkeypatch.setattr(agent_manager.shutil, "which", lambda name: "gemini.exe")
    monkeypatch.setattr(agent_manager, "is_dev_runtime", lambda: False)
    monkeypatch.setattr(subprocess, "CREATE_NEW_CONSOLE", 64, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 128, raising=False)

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["creationflags"] = kwargs.get("creationflags")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(agent_manager.subprocess, "run", fake_run)

    result = agent_manager.run_gemini("Proceed.", tmp_path, new_console=True)

    assert result.returncode == 0
    assert captured["creationflags"] == 128


def test_dev_runtime_forces_console_even_when_runner_does_not_request_it(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    monkeypatch.setattr(agent_manager.shutil, "which", lambda name: "codex.exe")
    monkeypatch.setattr(agent_manager, "is_dev_runtime", lambda: True)
    monkeypatch.setattr(subprocess, "CREATE_NEW_CONSOLE", 64, raising=False)
    monkeypatch.setattr(subprocess, "CREATE_NO_WINDOW", 128, raising=False)

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["creationflags"] = kwargs.get("creationflags")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(agent_manager.subprocess, "run", fake_run)

    result = agent_manager.run_codex("Proceed.", tmp_path, new_console=False)

    assert result.returncode == 0
    assert captured["creationflags"] == 64


def test_deliver_outputs_can_move_all_output_files(tmp_path):
    workspace = tmp_path / "workspace"
    output_dir = workspace / "output"
    nested_dir = output_dir / "nested"
    nested_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "card-1.md").write_text("question:\nA\nanswer:\nB\n", encoding="utf-8", newline="\n")
    (nested_dir / "card-2.txt").write_text("raw", encoding="utf-8", newline="\n")

    deliver_dir = tmp_path / "delivered"
    job = agent_manager.AgentJob(
        name="flashcard",
        runners=[],
        deliver_dir=deliver_dir,
        deliver_all_output_files=True,
        clean_markdown=True,
    )

    delivered = agent_manager._deliver_outputs(job, workspace)

    assert delivered == [
        deliver_dir / "card-1.md",
        deliver_dir / "nested" / "card-2.txt",
    ]
    assert (deliver_dir / "card-1.md").is_file()
    assert (deliver_dir / "nested" / "card-2.txt").is_file()


def test_deliver_outputs_preserves_existing_files_when_requested(tmp_path):
    workspace = tmp_path / "workspace"
    output_dir = workspace / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "card-1.md").write_text("new", encoding="utf-8", newline="\n")

    deliver_dir = tmp_path / "delivered"
    deliver_dir.mkdir(parents=True, exist_ok=True)
    (deliver_dir / "card-1.md").write_text("old", encoding="utf-8", newline="\n")

    job = agent_manager.AgentJob(
        name="flashcard",
        runners=[],
        deliver_dir=deliver_dir,
        deliver_all_output_files=True,
        preserve_existing_delivery=True,
        clean_markdown=False,
    )

    delivered = agent_manager._deliver_outputs(job, workspace)

    assert delivered == [deliver_dir / "card-1_1.md"]
    assert (deliver_dir / "card-1.md").read_text(encoding="utf-8") == "old"
    assert (deliver_dir / "card-1_1.md").read_text(encoding="utf-8") == "new"
