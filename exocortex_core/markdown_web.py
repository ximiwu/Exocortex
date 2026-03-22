from __future__ import annotations

import html
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .markdown import clean_markdown_text, normalize_paragraph_list_separation
from .paths import repo_root
from .text import read_text_auto, write_text_utf8

try:
    import markdown
except ImportError:  # pragma: no cover - optional dependency guard
    markdown = None

try:
    import pymdownx.arithmatex  # type: ignore  # noqa: F401

    _ARITHMETEX_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    _ARITHMETEX_AVAILABLE = False


_BOLD_SYMBOL_PATTERN = re.compile(r"\\mathbf\\s*\\{\\s*(\\\\[A-Za-z]+)\\s*\\}")
_DETAILS_TAG_PATTERN = re.compile(r"<details\b([^>]*)>", re.IGNORECASE)
_CLASS_ATTR_PATTERN = re.compile(r"\bclass\s*=\s*(\"([^\"]*)\"|'([^']*)')", re.IGNORECASE)
_MARKDOWN_ATTR_PATTERN = re.compile(r"\bmarkdown\s*=", re.IGNORECASE)
_DETAILS_BLOCK_PATTERN = re.compile(r"<details\b[^>]*>.*?</details>", re.IGNORECASE | re.DOTALL)

_KATEX_VERSION = "0.16.38"
_KATEX_CDN_BASE = f"https://cdn.jsdelivr.net/npm/katex@{_KATEX_VERSION}/dist"

def _katex_dist_dir() -> Path:
    return repo_root() / "web" / "node_modules" / "katex" / "dist"


def normalize_math_content(content: str) -> str:
    return _BOLD_SYMBOL_PATTERN.sub(r"\\boldsymbol{\1}", content)


def normalize_details_attrs(attrs: str) -> tuple[str, bool]:
    attrs_text = attrs
    class_match = _CLASS_ATTR_PATTERN.search(attrs_text)
    has_note = False
    if class_match:
        class_value = class_match.group(2) or class_match.group(3) or ""
        classes = class_value.split()
        has_note = "note" in classes or "note-container" in classes
        if has_note and "note-container" not in classes:
            classes.append("note-container")
            attrs_text = (
                attrs_text[: class_match.start()]
                + f' class="{" ".join(classes)}"'
                + attrs_text[class_match.end() :]
            )
    if not _MARKDOWN_ATTR_PATTERN.search(attrs_text):
        attrs_text = attrs_text.rstrip() + ' markdown="1"'
    return attrs_text, has_note


def normalize_note_content_divs(block: str) -> str:
    div_pattern = re.compile(r"<div\b([^>]*)>", re.IGNORECASE)

    def replace_div(match: re.Match[str]) -> str:
        attrs = match.group(1)
        if not _MARKDOWN_ATTR_PATTERN.search(attrs):
            return match.group(0)
        class_match = _CLASS_ATTR_PATTERN.search(attrs)
        if class_match:
            class_value = class_match.group(2) or class_match.group(3) or ""
            classes = class_value.split()
            if "note-content" not in classes:
                classes.append("note-content")
                attrs = (
                    attrs[: class_match.start()]
                    + f' class="{" ".join(classes)}"'
                    + attrs[class_match.end() :]
                )
        else:
            attrs = f' class="note-content"{attrs}'
        return f"<div{attrs}>"

    return div_pattern.sub(replace_div, block)


def normalize_details_markdown(content: str) -> str:
    def replace_block(match: re.Match[str]) -> str:
        block = match.group(0)
        tag_match = _DETAILS_TAG_PATTERN.search(block)
        if not tag_match:
            return block
        attrs = tag_match.group(1)
        new_attrs, has_note = normalize_details_attrs(attrs)
        block = block.replace(tag_match.group(0), f"<details{new_attrs}>", 1)
        if has_note:
            block = normalize_note_content_divs(block)
        return block

    return _DETAILS_BLOCK_PATTERN.sub(replace_block, content)


def _path_to_uri(path: Path) -> str:
    return path.resolve().as_uri()


def _directory_uri(path: Path) -> str:
    uri = _path_to_uri(path)
    return uri if uri.endswith("/") else f"{uri}/"


def katex_assets() -> str:
    katex_dir = _katex_dist_dir()
    if (katex_dir / "katex.min.js").is_file() and (katex_dir / "contrib" / "auto-render.min.js").is_file():
        base_url = _path_to_uri(katex_dir)
        return (
            f'<link rel="stylesheet" href="{base_url}/katex.min.css">'
            f'<script src="{base_url}/katex.min.js"></script>'
            f'<script src="{base_url}/contrib/copy-tex.min.js"></script>'
            f'<script src="{base_url}/contrib/auto-render.min.js"></script>'
        )
    return (
        f'<link rel="stylesheet" href="{_KATEX_CDN_BASE}/katex.min.css">'
        f'<script src="{_KATEX_CDN_BASE}/katex.min.js"></script>'
        f'<script src="{_KATEX_CDN_BASE}/contrib/copy-tex.min.js"></script>'
        f'<script src="{_KATEX_CDN_BASE}/contrib/auto-render.min.js"></script>'
    )


def render_markdown_content(content: str, *, base_url: str | None = None) -> str:
    if markdown is None:
        raise RuntimeError("Missing 'markdown' package.")

    extensions = ["extra", "sane_lists", "fenced_code", "tables"]
    extension_configs: dict[str, dict[str, object]] = {}
    if _ARITHMETEX_AVAILABLE:
        extensions.append("pymdownx.arithmatex")
        extension_configs["pymdownx.arithmatex"] = {"generic": True}

    normalized = normalize_math_content(content.lstrip("\ufeff"))
    normalized = normalize_details_markdown(normalized)
    normalized = normalize_paragraph_list_separation(normalized)

    md = markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    block_elements = md.block_level_elements
    if isinstance(block_elements, set):
        block_elements.update({"details", "summary"})
    else:
        for tag in ("details", "summary"):
            if tag not in block_elements:
                block_elements.append(tag)

    body = md.convert(normalized)

    styles = """
    body { font-family: 'Times New Roman','Segoe UI',sans-serif; font-size: 16px; line-height: 1.6; color: #333; padding: 16px; background: #fff; }
    p { margin: 0.6em 0; }
    pre { background: #f6f8fa; padding: 12px; border-radius: 6px; border: 1px solid #d0d7de; overflow-x: auto; }
    code { font-family: 'JetBrains Mono',monospace; font-size: 0.9em; background: rgba(175,184,193,0.2); padding: 0.2em 0.4em; border-radius: 4px; }
    img { max-width: 100%; border-radius: 4px; }
    table { border-collapse: collapse; width: 100%; margin: 12px 0; border: 1px solid #d0d7de; }
    th, td { border: 1px solid #d0d7de; padding: 10px 12px; }
    thead th { background: #f6f8fa; font-weight: 600; }
    details.note-container { background: #fff9e6; border-left: 5px solid #e6c200; margin: 15px 0; padding: 12px 16px; border-radius: 0 4px 4px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    details.note-container summary { font-weight: 700; color: #b38600; cursor: pointer; outline: none; }
    .note-content { margin-top: 10px; font-size: 0.95em; color: #4a4a4a; }
    .tab-wrapper { margin: 20px 0; border: 1px solid #dcdcdc; border-radius: 8px; overflow: hidden; background: #fff; box-shadow: 0 4px 10px rgba(0,0,0,0.08); border-left: 5px solid #1976d2; }
    .tab-header { display: flex; background: #f0f2f5; border-bottom: 1px solid #dcdcdc; overflow-x: auto; padding: 4px 4px 0; }
    .tab-wrapper:not(.expanded) .tab-header { border-bottom: none; background: #f8f9fa; }
    .tab-btn { flex: 1; padding: 10px 16px; margin: 0 2px; border: 1px solid transparent; border-bottom: none; background: none; cursor: pointer; font-weight: 600; font-size: 15px; color: #5f6368; border-radius: 6px 6px 0 0; min-width: 100px; position: relative; }
    .tab-btn:hover { background: #e4e6eb; color: #202124; }
    .tab-btn.active { background: #fff; color: #1a73e8; border-color: #dcdcdc; }
    .tab-btn.active::after { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: #1a73e8; }
    .tab-content-area { background: #fff; padding: 20px; display: none; border-top: 1px solid #dcdcdc; }
    .tab-wrapper.expanded .tab-content-area { display: block; }
    .tab-pane { display: none; animation: fadeEffect 0.3s; }
    .tab-pane.active { display: block; }
    @keyframes fadeEffect { from { opacity: 0; } to { opacity: 1; } }
    .tab-pane > details > summary { display: none; }
    .tab-pane > details.note-container { border: none; margin: 0; padding: 0; background: none; box-shadow: none; }
    """

    tabs_script = """
    <script>
    (function() {
        function initTabs() {
            const allDetails = Array.from(document.querySelectorAll('details'));
            const processed = new Set();
            allDetails.forEach(detail => {
                if (processed.has(detail)) return;
                const siblings = [detail];
                let next = detail.nextElementSibling;
                while (next) {
                    if (next.tagName && next.tagName.toLowerCase() === 'details') {
                        siblings.push(next);
                        processed.add(next);
                        next = next.nextElementSibling;
                    } else if (next.nodeType === 3 && !next.textContent.trim()) {
                        next = next.nextSibling;
                    } else {
                        break;
                    }
                }
                processed.add(detail);
                if (siblings.length < 2) return;
                const wrapper = document.createElement('div');
                wrapper.className = 'tab-wrapper';
                const header = document.createElement('div');
                header.className = 'tab-header';
                const contentArea = document.createElement('div');
                contentArea.className = 'tab-content-area';
                detail.parentNode.insertBefore(wrapper, detail);
                wrapper.appendChild(header);
                wrapper.appendChild(contentArea);
                siblings.forEach((item, index) => {
                    const summary = item.querySelector('summary');
                    const title = summary ? summary.textContent.trim() : ('Tab ' + (index + 1));
                    const btn = document.createElement('button');
                    btn.className = 'tab-btn';
                    btn.textContent = title;
                    const pane = document.createElement('div');
                    pane.className = 'tab-pane';
                    pane.appendChild(item);
                    item.open = true;
                    contentArea.appendChild(pane);
                    btn.onclick = () => {
                        const isActive = btn.classList.contains('active');
                        header.querySelectorAll('.tab-btn').forEach(node => node.classList.remove('active'));
                        contentArea.querySelectorAll('.tab-pane').forEach(node => node.classList.remove('active'));
                        if (isActive) {
                            wrapper.classList.remove('expanded');
                            return;
                        }
                        btn.classList.add('active');
                        pane.classList.add('active');
                        wrapper.classList.add('expanded');
                    };
                    header.appendChild(btn);
                });
            });
        }
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initTabs);
        } else {
            initTabs();
        }
    })();
    </script>
    """

    math_script = """
    <script>
    (function() {
        function renderMath() {
            if (typeof renderMathInElement !== 'function') {
                return false;
            }
            try {
                renderMathInElement(document.body, {
                    delimiters: [
                        { left: "$$", right: "$$", display: true },
                        { left: "\\\\[", right: "\\\\]", display: true },
                        { left: "$", right: "$", display: false },
                        { left: "\\\\(", right: "\\\\)", display: false }
                    ],
                    throwOnError: false
                });
                return true;
            } catch (_error) {
                return false;
            }
        }

        function initMath(retries) {
            if (renderMath()) {
                return;
            }
            if (retries <= 0) {
                return;
            }
            window.setTimeout(function() {
                initMath(retries - 1);
            }, 100);
        }

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', function() {
                initMath(20);
            });
        } else {
            initMath(20);
        }

        window.addEventListener('load', function() {
            initMath(20);
        });
    })();
    </script>
    """

    base_tag = f'<base href="{html.escape(base_url, quote=True)}">' if base_url else ""
    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset='UTF-8'>"
        f"{base_tag}<style>{styles}</style>{katex_assets()}"
        "</head><body>"
        f"{body}{tabs_script}{math_script}"
        "</body></html>"
    )


def _find_chromium_executable() -> Path | None:
    candidates: list[Path] = []
    for command in ("msedge", "chrome", "chromium", "brave"):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(Path(resolved))

    program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program_files_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    candidates.extend(
        [
            Path(program_files) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(program_files_x86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(local_app_data) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(program_files_x86) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(local_app_data) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(program_files) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(program_files_x86) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(local_app_data) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _render_pdf_with_playwright(html_path: Path, output_pdf: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:  # pragma: no cover - optional dependency guard
        raise RuntimeError("Playwright is not available.") from exc

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(html_path.as_uri(), wait_until="networkidle")
            page.wait_for_timeout(750)
            page.pdf(path=str(output_pdf), print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()


def _render_pdf_with_chromium(html_path: Path, output_pdf: Path, profile_dir: Path) -> None:
    browser = _find_chromium_executable()
    if browser is None:
        raise RuntimeError("No Chromium-based browser was found for headless PDF rendering.")

    completed = subprocess.run(
        [
            str(browser),
            "--headless",
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=3000",
            f"--user-data-dir={profile_dir}",
            f"--print-to-pdf={output_pdf}",
            html_path.as_uri(),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if completed.returncode != 0 or not output_pdf.is_file():
        detail = (completed.stderr or completed.stdout or "").strip() or f"exit code {completed.returncode}"
        raise RuntimeError(f"Chromium PDF render failed: {detail}")


def render_markdown_asset_to_pdf(markdown_path: Path, output_pdf: Path) -> Path:
    markdown_path = Path(markdown_path)
    output_pdf = Path(output_pdf)
    if not markdown_path.is_file():
        raise FileNotFoundError(f"Markdown not found: {markdown_path}")

    content = clean_markdown_text(read_text_auto(markdown_path))
    html_text = render_markdown_content(content, base_url=_directory_uri(markdown_path.parent))
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    output_pdf.unlink(missing_ok=True)

    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="markdown_pdf_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        html_path = temp_dir / "render.html"
        profile_dir = temp_dir / "profile"
        write_text_utf8(html_path, html_text)

        for renderer in (
            lambda: _render_pdf_with_playwright(html_path, output_pdf),
            lambda: _render_pdf_with_chromium(html_path, output_pdf, profile_dir),
        ):
            try:
                renderer()
            except Exception as exc:
                errors.append(str(exc))
                continue
            if output_pdf.is_file():
                return output_pdf

    raise RuntimeError(
        f"Failed to render markdown to PDF for {markdown_path}: {' | '.join(errors) or 'unknown error'}"
    )


__all__ = [
    "katex_assets",
    "normalize_details_attrs",
    "normalize_details_markdown",
    "normalize_math_content",
    "normalize_note_content_divs",
    "normalize_paragraph_list_separation",
    "render_markdown_asset_to_pdf",
    "render_markdown_content",
]
