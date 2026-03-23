from __future__ import annotations

from pathlib import Path

from .paths import agent_workspace_root, exocortex_assets_root, repo_root


REPO_ROOT = repo_root()
PROMPTS_DIR = REPO_ROOT / "prompts"
ASSETS_ROOT = exocortex_assets_root()
WORKSPACE_ROOT = agent_workspace_root(root=REPO_ROOT)

CODEX_MODEL = "gpt-5.4"
GEMINI_MODEL = "gemini-3-pro-preview"
CODEX_REASONING_LOW = "low"
CODEX_REASONING_HIGH = "high"
CODEX_REASONING_XHIGH = "xhigh"
CODEX_REASONING_MEDIUM = "medium"


def prompt_path(*parts: str) -> Path:
    return PROMPTS_DIR.joinpath(*parts)


IMG2MD_CODEX_PROMPT = prompt_path("img2md", "codex", "AGENTS.md")
IMG2MD_GEMINI_PROMPT = prompt_path("img2md", "gemini", "GEMINI.md")
IMG_EXPLAINER_CODEX_PROMPT = prompt_path("img_explainer", "codex", "AGENTS.md")
IMG_EXPLAINER_CODEX_2_PROMPT = prompt_path("img_explainer", "codex_2", "AGENTS.md")
MD_EXPLAINER_CODEX_PROMPT = prompt_path("md_explainer", "codex", "AGENTS.md")
MD_EXPLAINER_CODEX_2_PROMPT = prompt_path("md_explainer", "codex_2", "AGENTS.md")
ENHANCER_CODEX_PROMPT = prompt_path("enhancer", "codex", "AGENTS.md")
INTEGRATOR_CODEX_PROMPT = prompt_path("integrator", "codex", "AGENTS.md")
TUTOR_CODEX_PROMPT = prompt_path("tutor", "codex", "AGENTS.md")
BUG_FINDER_GEMINI_PROMPT = prompt_path("bug_finder", "gemini", "GEMINI.md")
RE_TUTOR_GEMINI_PROMPT = prompt_path("re_tutor", "gemini", "GEMINI.md")
MANUSCRIPT_GEMINI_PROMPT = prompt_path("manuscript2md", "gemini", "GEMINI.md")
LATEX_FIXER_CODEX_PROMPT = prompt_path("latex_fixer", "codex", "AGENTS.md")

EXTRACTOR_PROMPTS: dict[str, Path] = {
    "background": prompt_path("extractor", "background", "codex", "AGENTS.md"),
    "concept": prompt_path("extractor", "concept", "codex", "AGENTS.md"),
    "formula": prompt_path("extractor", "formula", "codex", "AGENTS.md"),
}


def relative_to_repo(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


__all__ = [
    "ASSETS_ROOT",
    "BUG_FINDER_GEMINI_PROMPT",
    "CODEX_MODEL",
    "CODEX_REASONING_HIGH",
    "CODEX_REASONING_LOW",
    "CODEX_REASONING_MEDIUM",
    "CODEX_REASONING_XHIGH",
    "ENHANCER_CODEX_PROMPT",
    "EXTRACTOR_PROMPTS",
    "GEMINI_MODEL",
    "IMG2MD_CODEX_PROMPT",
    "IMG2MD_GEMINI_PROMPT",
    "IMG_EXPLAINER_CODEX_2_PROMPT",
    "IMG_EXPLAINER_CODEX_PROMPT",
    "INTEGRATOR_CODEX_PROMPT",
    "LATEX_FIXER_CODEX_PROMPT",
    "MANUSCRIPT_GEMINI_PROMPT",
    "MD_EXPLAINER_CODEX_2_PROMPT",
    "MD_EXPLAINER_CODEX_PROMPT",
    "PROMPTS_DIR",
    "REPO_ROOT",
    "RE_TUTOR_GEMINI_PROMPT",
    "TUTOR_CODEX_PROMPT",
    "WORKSPACE_ROOT",
    "prompt_path",
    "relative_to_repo",
    "resolve_repo_path",
]
