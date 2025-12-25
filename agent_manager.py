from __future__ import annotations

import logging
import os
import re
import shutil
import stat
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


def _detect_repo_root(module_dir: Path) -> Path:
    markers = ("prompts", "assets", "agent_workspace", "README.md")
    for candidate in (module_dir, *module_dir.parents):
        if any((candidate / marker).exists() for marker in markers):
            return candidate
    return module_dir


REPO_ROOT = _detect_repo_root(Path(__file__).resolve().parent)
WORKSPACE_ROOT = REPO_ROOT / "agent_workspace"
_WORKSPACE_LOCK = threading.Lock()
_WORKSPACE_INITIALIZED = False


def _safe_rmtree(path: Path) -> None:
    """Remove a directory tree, clearing read-only flags on Windows if needed."""

    def _handle_remove_readonly(func, target, exc_info):
        try:
            os.chmod(target, stat.S_IWRITE)
        except Exception:
            pass
        func(target)

    shutil.rmtree(path, onerror=_handle_remove_readonly)


def _safe_unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except PermissionError:
        try:
            os.chmod(path, stat.S_IWRITE)
        except Exception:
            pass
        path.unlink(missing_ok=True)


def _ensure_workspace_root() -> None:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


def _read_counter(counter_path: Path) -> int | None:
    try:
        value = int(counter_path.read_text(encoding="utf-8").strip())
    except Exception:
        return None
    return value if value > 0 else None


def _next_workspace_id() -> int:
    counter_path = WORKSPACE_ROOT / ".counter"
    current = _read_counter(counter_path)
    if current is None:
        ids = []
        for entry in WORKSPACE_ROOT.iterdir():
            if not entry.is_dir():
                continue
            try:
                ids.append(int(entry.name))
            except Exception:
                continue
        current = max(ids, default=0) + 1
    counter_path.write_text(str(current + 1), encoding="utf-8")
    return current


def _reset_workspace_root() -> None:
    if not WORKSPACE_ROOT.exists():
        WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
        return
    for entry in WORKSPACE_ROOT.iterdir():
        try:
            if entry.is_dir():
                _safe_rmtree(entry)
            else:
                _safe_unlink(entry)
        except Exception:
            logger.warning("Failed to remove workspace entry: %s", entry)


def _initialize_workspace_root() -> None:
    global _WORKSPACE_INITIALIZED
    if _WORKSPACE_INITIALIZED:
        return
    with _WORKSPACE_LOCK:
        if _WORKSPACE_INITIALIZED:
            return
        _ensure_workspace_root()
        _reset_workspace_root()
        _WORKSPACE_INITIALIZED = True


_initialize_workspace_root()


def create_workspace() -> Path:
    _initialize_workspace_root()
    with _WORKSPACE_LOCK:
        workspace_id = _next_workspace_id()
        workspace = WORKSPACE_ROOT / str(workspace_id)
        while workspace.exists():
            workspace_id = _next_workspace_id()
            workspace = WORKSPACE_ROOT / str(workspace_id)
        workspace.mkdir(parents=True, exist_ok=False)
    return workspace


def _copy_files(
    sources: Iterable[Path],
    destination_dir: Path,
    rename: dict[str, str] | None = None,
) -> list[Path]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    rename = rename or {}
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")
        target_name = rename.get(source.name, source.name)
        destination = destination_dir / target_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.unlink(missing_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def clean_markdown_file(file_path: Path) -> None:
    content = file_path.read_text(encoding="utf-8-sig")

    def fix_latex_syntax(text: str) -> str:
        return text.replace("\\\\", "\\")

    content = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", content, flags=re.DOTALL)
    content = re.sub(r"\\\((.*?)\\\)", r"$\1$", content, flags=re.DOTALL)

    def clean_inline(match: re.Match[str]) -> str:
        inner = fix_latex_syntax(match.group(1))
        inner = inner.replace("\u00A0", " ").replace("\u3000", " ").strip()
        return f"${inner}$"

    content = re.sub(
        r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", clean_inline, content, flags=re.DOTALL
    )

    pattern = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)

    def reform_block(match: re.Match[str]) -> str:
        math_content = fix_latex_syntax(match.group(1))
        lines = math_content.splitlines()
        clean_lines = []
        for line in lines:
            stripped = line.strip().replace("\u00A0", " ").replace("\u3000", " ")
            stripped = stripped.replace("\u200b", " ").replace("\ufeff", " ")
            if stripped:
                clean_lines.append(stripped)
        cleaned_math_body = "\n".join(clean_lines)
        return f"\n\n$$\n{cleaned_math_body}\n$$\n\n"

    new_content = pattern.sub(reform_block, content)

    lines = new_content.splitlines()
    processed_lines = []
    in_code_block = False
    strip_chars = " \t\u00A0\u3000"

    for line in lines:
        if re.match(r"^\s*```", line):
            in_code_block = not in_code_block
            processed_lines.append(line.lstrip(strip_chars))
            continue
        if in_code_block:
            processed_lines.append(line)
        else:
            processed_lines.append(line.lstrip(strip_chars))

    new_content = "\n".join(processed_lines)
    new_content = re.sub(r"\n{3,}", "\n\n", new_content)

    file_path.write_text(new_content, encoding="utf-8", newline="\n")


def merge_outputs(
    directory: Path,
    pattern: str,
    merged_name: str,
    *,
    separator: str = "\n\n",
    delete_sources: bool = True,
) -> Path:
    pattern_re = re.compile(pattern, re.IGNORECASE)
    files = [
        path
        for path in directory.iterdir()
        if path.is_file() and pattern_re.match(path.name)
    ]
    if not files:
        raise FileNotFoundError(f"No files matched '{pattern}' under {directory}")

    def sort_key(path: Path) -> tuple[int, str]:
        match = pattern_re.match(path.name)
        if match and match.groups():
            for group in match.groups():
                if group.isdigit():
                    return int(group), path.name
            return 0, match.group(1)
        return 0, path.name

    files.sort(key=sort_key)
    merged_path = directory / merged_name
    merged_content = separator.join(path.read_text(encoding="utf-8") for path in files)
    merged_path.write_text(
        merged_content + ("\n" if merged_content else ""), encoding="utf-8"
    )
    if delete_sources:
        for path in files:
            path.unlink(missing_ok=True)
    return merged_path


def run_codex(
    message: str,
    workdir: Path,
    *,
    model: str = "gpt-5.2",
    model_reasoning_effort: str = "high",
    new_console: bool = False,
) -> subprocess.CompletedProcess[str]:
    codex_exe = shutil.which("codex")
    if not codex_exe:
        path_env = os.environ.get("PATH", "")
        raise FileNotFoundError(f"`codex` not found on PATH; current PATH={path_env}")

    creation_flags = 0
    if new_console and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
        creation_flags = subprocess.CREATE_NEW_CONSOLE

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
            message,
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


RunnerCallback = Callable[[str, "RunnerConfig", Path, Exception | None], None]


@dataclass(frozen=True)
class RunnerConfig:
    runner: str  # "codex" or "gemini"
    prompt_path: Path
    model: str
    reasoning_effort: str | None = None
    new_console: bool = True
    extra_message: str | None = None
    prompt_filename: str | None = None


@dataclass
class AgentCallbacks:
    on_start: RunnerCallback | None = None
    on_finish: RunnerCallback | None = None
    on_failure: RunnerCallback | None = None


@dataclass
class AgentJob:
    name: str
    runners: list[RunnerConfig]
    input_files: list[Path] = field(default_factory=list)
    input_rename: dict[str, str] = field(default_factory=dict)
    reference_files: list[Path] = field(default_factory=list)
    reference_rename: dict[str, str] = field(default_factory=dict)
    output_seed_files: list[Path] = field(default_factory=list)
    output_rename: dict[str, str] = field(default_factory=dict)
    deliver_dir: Path | None = None
    deliver_rename: dict[str, str] = field(default_factory=dict)
    clean_markdown: bool = True
    callbacks: AgentCallbacks | None = None


@dataclass(frozen=True)
class AgentRunResult:
    job: AgentJob
    workspace: Path
    delivered: list[Path]
    exit_codes: dict[str, int]


def _build_message(extra_message: str | None = None) -> str:
    if extra_message and extra_message.strip():
        return extra_message
    return "Proceed."


def _copy_prompt(prompt_path: Path, workspace: Path, dest_name: str | None = None) -> Path:
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Prompt not found: {prompt_path}")
    destination = workspace / (dest_name or prompt_path.name)
    destination.unlink(missing_ok=True)
    shutil.copy2(prompt_path, destination)
    return destination


def _prepare_workspace(job: AgentJob, workspace: Path) -> None:
    for runner in job.runners:
        _copy_prompt(runner.prompt_path, workspace, runner.prompt_filename)

    input_dir = workspace / "input"
    output_dir = workspace / "output"
    references_dir = workspace / "references"

    _copy_files(job.input_files, input_dir, job.input_rename)
    _copy_files(job.reference_files, references_dir, job.reference_rename)
    _copy_files(job.output_seed_files, output_dir, job.output_rename)


def _deliver_outputs(job: AgentJob, workspace: Path) -> list[Path]:
    if job.deliver_dir is None:
        return []
    output_dir = workspace / "output"
    if job.clean_markdown and output_dir.is_dir():
        for path in output_dir.iterdir():
            if path.is_file() and path.suffix.lower() == ".md":
                clean_markdown_file(path)

    deliver_dir = job.deliver_dir
    if not deliver_dir.is_absolute():
        deliver_dir = (REPO_ROOT / deliver_dir).resolve()
    deliver_dir.mkdir(parents=True, exist_ok=True)

    delivered: list[Path] = []
    for src_name, target_name in (job.deliver_rename or {}).items():
        source = output_dir / src_name
        if not source.is_file():
            raise FileNotFoundError(f"Expected output not found: {source}")
        destination = deliver_dir / target_name
        destination.unlink(missing_ok=True)
        delivered.append(Path(shutil.move(str(source), destination)))
    return delivered


def _launch_runner(
    job: AgentJob,
    runner: RunnerConfig,
    workspace: Path,
) -> int:
    callbacks = job.callbacks
    if callbacks and callbacks.on_start:
        callbacks.on_start(job.name, runner, workspace, None)

    try:
        message = _build_message(runner.extra_message)
        if runner.runner == "codex":
            run_codex(
                message,
                workspace,
                model=runner.model,
                model_reasoning_effort=runner.reasoning_effort or "high",
                new_console=runner.new_console,
            )
        elif runner.runner == "gemini":
            run_gemini(
                message,
                workspace,
                model=runner.model,
                new_console=runner.new_console,
            )
        else:
            raise ValueError(f"Unknown runner: {runner.runner}")
    except Exception as exc:
        if callbacks and callbacks.on_failure:
            callbacks.on_failure(job.name, runner, workspace, exc)
        if isinstance(exc, subprocess.CalledProcessError):
            return exc.returncode or 1
        return 1

    if callbacks and callbacks.on_finish:
        callbacks.on_finish(job.name, runner, workspace, None)
    return 0


def run_agent_job(job: AgentJob) -> AgentRunResult:
    workspace = create_workspace()
    try:
        _prepare_workspace(job, workspace)

        exit_codes: dict[str, int] = {}
        with ThreadPoolExecutor(max_workers=len(job.runners) or 1) as executor:
            futures = {
                executor.submit(_launch_runner, job, runner, workspace): runner
                for runner in job.runners
            }
            for future in futures:
                runner = futures[future]
                exit_codes[runner.runner] = future.result()

        failures = {name: code for name, code in exit_codes.items() if code != 0}
        if failures:
            raise RuntimeError(f"Agent '{job.name}' failed: {failures}")

        delivered = _deliver_outputs(job, workspace)
        return AgentRunResult(
            job=job, workspace=workspace, delivered=delivered, exit_codes=exit_codes
        )
    finally:
        try:
            if workspace.exists():
                _safe_rmtree(workspace)
        except Exception:
            logger.warning("Failed to remove workspace: %s", workspace)


def run_agent_jobs(jobs: Iterable[AgentJob], *, max_workers: int | None = None) -> list[AgentRunResult]:
    job_list = list(jobs)
    if not job_list:
        return []
    results: list[AgentRunResult] = []
    with ThreadPoolExecutor(max_workers=max_workers or len(job_list)) as executor:
        futures = {executor.submit(run_agent_job, job): job for job in job_list}
        for future in futures:
            results.append(future.result())
    return results
