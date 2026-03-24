from __future__ import annotations

import subprocess
from pathlib import Path

import agent_manager


def test_new_console_requested_only_in_dev_runtime(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    monkeypatch.setattr(agent_manager.shutil, "which", lambda name: "codex.exe")
    monkeypatch.setattr(agent_manager, "is_dev_runtime", lambda: True)
    monkeypatch.setattr(subprocess, "CREATE_NEW_CONSOLE", 64, raising=False)

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

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["creationflags"] = kwargs.get("creationflags")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(agent_manager.subprocess, "run", fake_run)

    result = agent_manager.run_gemini("Proceed.", tmp_path, new_console=True)

    assert result.returncode == 0
    assert captured["creationflags"] == 0
