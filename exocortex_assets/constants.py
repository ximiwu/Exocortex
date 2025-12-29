from __future__ import annotations

from pathlib import Path

from exocortex_core.paths import repo_root


REPO_ROOT = repo_root()
PROMPTS_DIR = REPO_ROOT / "prompts"
ASSETS_ROOT = REPO_ROOT / "assets"

REFERENCE_RENDER_DPI = 130  # Keep in sync with pdf_block_gui_lib.main_window.DEFAULT_RENDER_DPI

EXTRACTOR_AGENTS: tuple[str, ...] = ("background", "concept", "formula")

CODEX_MODEL = "gpt-5.2"
CODEX_REASONING_XHIGH = "xhigh"
CODEX_REASONING_HIGH = "high"
CODEX_REASONING_MEDIUM = "medium"
GEMINI_MODEL = "gemini-3-pro-preview"


def relative_to_repo(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def prompt_path(*parts: str) -> Path:
    return PROMPTS_DIR.joinpath(*parts)


IMG2MD_CODEX_PROMPT = prompt_path("img2md", "codex", "AGENTS.md")
IMG2MD_GEMINI_PROMPT = prompt_path("img2md", "gemini", "GEMINI.md")
IMG_EXPLAINER_CODEX_PROMPT = prompt_path("img_explainer", "codex", "AGENTS.md")
IMG_EXPLAINER_GEMINI_PROMPT = prompt_path("img_explainer", "gemini", "GEMINI.md")
ENHANCER_GEMINI_PROMPT = prompt_path("enhancer", "gemini", "GEMINI.md")
INTEGRATOR_CODEX_PROMPT = prompt_path("integrator", "codex", "AGENTS.md")
TUTOR_GEMINI_PROMPT = prompt_path("tutor", "gemini", "GEMINI.md")
BUG_FINDER_GEMINI_PROMPT = prompt_path("bug_finder", "gemini", "GEMINI.md")
RE_TUTOR_GEMINI_PROMPT = prompt_path("re_tutor", "gemini", "GEMINI.md")
MANUSCRIPT_GEMINI_PROMPT = prompt_path("manuscript2md", "gemini", "GEMINI.md")
LATEX_FIXER_GEMINI_PROMPT = prompt_path("latex_fixer", "GEMINI.md")

EXTRACTOR_PROMPTS = {
    "background": prompt_path("extractor", "background", "codex", "AGENTS.md"),
    "concept": prompt_path("extractor", "concept", "codex", "AGENTS.md"),
    "formula": prompt_path("extractor", "formula", "codex", "AGENTS.md"),
}

EXTRACTOR_OUTPUT_NAMES = {
    "background": "background.md",
    "concept": "concept.md",
    "formula": "formula.md",
}

