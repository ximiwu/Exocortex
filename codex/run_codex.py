from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def run_codex(
    message: str,
    workdir: Path,
    *,
    model: str = "gpt-5.2",
    model_reasoning_effort: str = "high",
    new_console: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Invoke `codex` in the target workdir with the given prompt."""
    codex_exe = shutil.which("codex")
    if not codex_exe:
        path_env = os.environ.get("PATH", "")
        raise FileNotFoundError(f"`codex` not found on PATH; current PATH={path_env}")

    creation_flags = 0
    if new_console and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
        creation_flags = subprocess.CREATE_NEW_CONSOLE

    message_arg = f'"{message}"'

    return subprocess.run(
        [
            codex_exe,
            "exec",
            "--skip-git-repo-check",
            "--sandbox",
            "danger-full-access",
            "--model",
            model,
            "-c",
            f'model_reasoning_effort="{model_reasoning_effort}"',
            "--",
            message_arg,
        ],
        cwd=workdir,
        check=True,
        creationflags=creation_flags,
    )


def run_gemini(
    message: str,
    workdir: Path,
    *,
    model: str = "gemini-3-pro-preview",
    new_console: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Invoke `gemini` in the target workdir with the given prompt."""
    gemini_exe = shutil.which("gemini")
    if not gemini_exe:
        path_env = os.environ.get("PATH", "")
        raise FileNotFoundError(f"`gemini` not found on PATH; current PATH={path_env}")

    creation_flags = 0
    if new_console and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
        creation_flags = subprocess.CREATE_NEW_CONSOLE

    return subprocess.run(
        [
            gemini_exe,
            "--model",
            model,
            "--yolo",
            message,
        ],
        cwd=workdir,
        check=True,
        creationflags=creation_flags,
    )
