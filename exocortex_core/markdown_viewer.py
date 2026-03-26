from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from .markdown import clean_markdown_text, normalize_paragraph_list_separation
from .markdown_web import katex_asset_dir, katex_assets, normalize_details_markdown, normalize_math_content

try:
    import markdown as py_markdown
except ImportError:  # pragma: no cover - dependency guard
    py_markdown = None

try:
    import pymdownx.arithmatex  # type: ignore  # noqa: F401

    _ARITHMATEX_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency guard
    _ARITHMATEX_AVAILABLE = False


_KATEX_MEDIA_FILES = (
    Path("katex.min.js"),
    Path("contrib") / "auto-render.min.js",
    Path("contrib") / "copy-tex.min.js",
)

_KATEX_CSS_URL_PATTERN = re.compile(r"url\((['\"]?)fonts/([^'\")]+)\1\)")

_VIEWER_LIGHT_CSS = """
:root {
  color-scheme: light;
  --font-markdown-body: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
  --font-markdown-heading: "Aptos", "Segoe UI Variable", "Trebuchet MS", sans-serif;
  --font-markdown-code: "Cascadia Code", "Consolas", monospace;
  --bg-paper: #fffdf8;
  --bg-paper-soft: #f7f4ed;
  --line-strong: rgba(34, 53, 63, 0.16);
  --ink-strong: #1b252c;
  --ink-body: #30414b;
  --ink-soft: #62717a;
  --accent: #125c61;
  --accent-strong: #0c4c50;
  --accent-warm: #b07b3b;
  --surface-accent-soft: rgba(18, 92, 97, 0.08);
  --surface-code: #f3efe6;
  --surface-note: #fdf5e6;
  --border-subtle: rgba(34, 53, 63, 0.08);
  --border-default: rgba(34, 53, 63, 0.1);
}

body {
  margin: 0;
  background: var(--bg-paper);
  color: var(--ink-strong);
  padding: 18px;
}

.markdown-rendered {
  color: var(--ink-body);
  line-height: 1.7;
  font-family: var(--font-markdown-body);
  font-size: 1.04rem;
}

.markdown-rendered > :first-child {
  margin-top: 0;
}

.markdown-rendered h1,
.markdown-rendered h2,
.markdown-rendered h3,
.markdown-rendered h4 {
  color: var(--ink-strong);
  font-family: var(--font-markdown-heading);
  line-height: 1.2;
}

.markdown-rendered h1 {
  margin: 0 0 1.1rem;
  font-size: 2rem;
}

.markdown-rendered h2 {
  margin-top: 1.9rem;
  font-size: 1.35rem;
}

.markdown-rendered p,
.markdown-rendered ul,
.markdown-rendered ol,
.markdown-rendered blockquote,
.markdown-rendered table,
.markdown-rendered details,
.markdown-rendered pre {
  margin: 1rem 0;
}

.markdown-rendered a {
  color: var(--accent);
}

.markdown-rendered code {
  padding: 0.18em 0.42em;
  border-radius: 7px;
  background: var(--surface-accent-soft);
  font-family: var(--font-markdown-code);
  font-size: 0.92em;
}

.markdown-rendered pre {
  overflow: auto;
  padding: 14px 16px;
  border: 1px solid var(--border-default);
  border-radius: 16px;
  background: var(--surface-code);
}

.markdown-rendered pre code {
  padding: 0;
  background: transparent;
}

.markdown-rendered table {
  width: 100%;
  border-collapse: collapse;
  border: 1px solid var(--line-strong);
  overflow: hidden;
  border-radius: 14px;
}

.markdown-rendered th,
.markdown-rendered td {
  padding: 11px 12px;
  border: 1px solid var(--border-default);
  text-align: left;
}

.markdown-rendered thead th {
  background: var(--surface-accent-soft);
  font-family: var(--font-markdown-heading);
}

.markdown-rendered img {
  max-width: 100%;
  border-radius: 14px;
}

.markdown-rendered details {
  border: 1px solid var(--line-strong);
  border-radius: 16px;
  background: var(--bg-paper-soft);
  overflow: hidden;
}

.markdown-rendered details > summary {
  cursor: pointer;
  padding: 14px 16px;
  font-family: var(--font-markdown-heading);
  font-weight: 700;
  color: var(--ink-strong);
}

.markdown-rendered details[open] > summary {
  border-bottom: 1px solid var(--border-subtle);
}

.markdown-rendered details > :not(summary) {
  margin-left: 16px;
  margin-right: 16px;
}

.markdown-rendered details.note-container {
  border-left: 5px solid var(--accent-warm);
  background: var(--surface-note);
}

.markdown-rendered .note-content {
  padding-bottom: 16px;
}

.markdown-tab-group {
  margin: 1.25rem 0;
  border: 1px solid var(--line-strong);
  border-radius: 18px;
  background: var(--bg-paper-soft);
}

.markdown-tab-group__tabs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding: 8px 8px 0;
  border-bottom: 1px solid var(--border-subtle);
}

.markdown-tab-group__tab {
  flex: 1;
  min-width: 120px;
  padding: 10px 12px;
  border: 1px solid transparent;
  border-bottom: none;
  border-radius: 12px 12px 0 0;
  background: transparent;
  color: var(--ink-soft);
  font-weight: 700;
  cursor: pointer;
}

.markdown-tab-group__tab:hover {
  background: var(--surface-accent-soft);
}

.markdown-tab-group__tab.is-active {
  color: var(--accent-strong);
  background: var(--bg-paper);
  border-color: var(--border-default);
}

.markdown-tab-group__content {
  padding: 0 16px 16px;
}

.markdown-tab-group__pane {
  display: none;
}

.markdown-tab-group__pane.is-active {
  display: block;
}

.markdown-tab-group__pane > details {
  margin: 0;
  border: none;
  background: transparent;
}

.markdown-tab-group__pane > details > summary {
  display: none;
}
""".strip()

_VIEWER_ENHANCEMENT_SCRIPT = """
(function () {
  function ensureNoteContainers(root) {
    root.querySelectorAll("details").forEach(function (element) {
      var detail = element;
      if (detail.classList.contains("note") && !detail.classList.contains("note-container")) {
        detail.classList.add("note-container");
      }

      if (!detail.classList.contains("note-container")) {
        return;
      }

      var summary = detail.querySelector(":scope > summary");
      var existingContent = detail.querySelector(":scope > .note-content");
      if (existingContent) {
        return;
      }

      var wrapper = document.createElement("div");
      wrapper.className = "note-content";

      Array.from(detail.childNodes).forEach(function (child) {
        if (summary && child === summary) {
          return;
        }
        wrapper.appendChild(child);
      });

      detail.appendChild(wrapper);
    });
  }

  function createDetailsTabGroup(detailsList) {
    if (detailsList.length < 2) {
      return;
    }

    var parent = detailsList[0].parentElement;
    if (!parent) {
      return;
    }

    var wrapper = document.createElement("div");
    wrapper.className = "markdown-tab-group is-expanded";

    var header = document.createElement("div");
    header.className = "markdown-tab-group__tabs";

    var content = document.createElement("div");
    content.className = "markdown-tab-group__content";

    parent.insertBefore(wrapper, detailsList[0]);
    wrapper.appendChild(header);
    wrapper.appendChild(content);

    detailsList.forEach(function (detail, index) {
      var summary = detail.querySelector(":scope > summary");
      var title = (summary && summary.textContent && summary.textContent.trim()) || ("Tab " + (index + 1));
      var button = document.createElement("button");
      button.type = "button";
      button.className = "markdown-tab-group__tab";
      button.textContent = title;

      var pane = document.createElement("div");
      pane.className = "markdown-tab-group__pane";

      detail.open = true;
      pane.appendChild(detail);
      content.appendChild(pane);
      header.appendChild(button);

      button.addEventListener("click", function () {
        var isActive = button.classList.contains("is-active");

        header.querySelectorAll(".markdown-tab-group__tab").forEach(function (tab) {
          tab.classList.remove("is-active");
        });
        content.querySelectorAll(".markdown-tab-group__pane").forEach(function (currentPane) {
          currentPane.classList.remove("is-active");
        });

        if (isActive) {
          wrapper.classList.remove("is-expanded");
          return;
        }

        wrapper.classList.add("is-expanded");
        button.classList.add("is-active");
        pane.classList.add("is-active");
      });

      if (index === 0) {
        button.classList.add("is-active");
        pane.classList.add("is-active");
      }
    });
  }

  function buildDetailsTabGroups(root) {
    var candidateParents = new Set();
    root.querySelectorAll("details").forEach(function (detail) {
      var parent = detail.parentElement;
      if (!parent) {
        return;
      }
      if (parent.classList.contains("markdown-tab-group__pane")) {
        return;
      }
      candidateParents.add(parent);
    });

    candidateParents.forEach(function (parent) {
      var currentRun = [];

      function flush() {
        if (currentRun.length >= 2) {
          createDetailsTabGroup(currentRun.slice());
        }
        currentRun.length = 0;
      }

      Array.from(parent.childNodes).forEach(function (node) {
        if (node.nodeType === Node.TEXT_NODE) {
          if (!node.textContent || !node.textContent.trim()) {
            return;
          }
          flush();
          return;
        }

        if (node instanceof HTMLDetailsElement) {
          currentRun.push(node);
          return;
        }

        flush();
      });

      flush();
    });
  }

  function unwrapMathDelimiters(value) {
    var text = value.trim();
    var delimiterPairs = [
      { left: "\\\\[", right: "\\\\]", displayMode: true },
      { left: "$$", right: "$$", displayMode: true },
      { left: "\\\\(", right: "\\\\)", displayMode: false },
      { left: "$", right: "$", displayMode: false }
    ];

    for (var index = 0; index < delimiterPairs.length; index += 1) {
      var delimiter = delimiterPairs[index];
      if (text.startsWith(delimiter.left) && text.endsWith(delimiter.right)) {
        return {
          tex: text.slice(delimiter.left.length, text.length - delimiter.right.length).trim(),
          displayMode: delimiter.displayMode
        };
      }
    }

    return { tex: text, displayMode: false };
  }

  function renderArithmatexNodes(root) {
    root.querySelectorAll(".arithmatex").forEach(function (element) {
      if (element.dataset.mathRendered === "true") {
        return;
      }

      var source = unwrapMathDelimiters(element.textContent || "");
      if (!source.tex) {
        element.dataset.mathRendered = "true";
        return;
      }

      try {
        katex.render(source.tex, element, {
          displayMode: source.displayMode,
          throwOnError: false,
          strict: "ignore"
        });
        element.dataset.mathRendered = "true";
      } catch (_error) {
      }
    });
  }

  function enhanceMathContent(root) {
    try {
      var hasArithmatexNodes = root.querySelector(".arithmatex") !== null;
      if (hasArithmatexNodes) {
        renderArithmatexNodes(root);
        return;
      }

      if (typeof renderMathInElement !== "function") {
        return;
      }

      renderMathInElement(root, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "\\\\[", right: "\\\\]", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\\\(", right: "\\\\)", display: false }
        ],
        throwOnError: false
      });
    } catch (_error) {
    }
  }

  function enhanceMarkdownContent(root) {
    ensureNoteContainers(root);
    buildDetailsTabGroups(root);
    enhanceMathContent(root);
  }

  function run(rootSelector) {
    document.querySelectorAll(rootSelector).forEach(function (root) {
      enhanceMarkdownContent(root);
    });
  }

  window.ExocortexMarkdownViewer = {
    enhance: enhanceMarkdownContent,
    run: run
  };
})();
""".strip()


@dataclass(frozen=True)
class RenderedMarkdownViewerDocument:
    normalized_markdown: str
    body_html: str
    head_html: str
    full_html: str


@dataclass(frozen=True)
class AnkiMarkdownViewerAssets:
    css: str
    scripts_html: str
    media_files: tuple[Path, ...]


def _render_markdown_body(content: str) -> tuple[str, str]:
    if py_markdown is None:
        raise RuntimeError("Missing 'markdown' package.")
    if not _ARITHMATEX_AVAILABLE:
        raise RuntimeError("Missing 'pymdown-extensions' package.")

    normalized = clean_markdown_text(content)
    normalized = normalize_math_content(normalized)
    normalized = normalize_details_markdown(normalized)
    normalized = normalize_paragraph_list_separation(normalized)

    extensions = ["extra", "sane_lists", "fenced_code", "tables", "pymdownx.arithmatex"]
    extension_configs = {"pymdownx.arithmatex": {"generic": True}}
    renderer = py_markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    block_elements = renderer.block_level_elements
    if isinstance(block_elements, set):
        block_elements.update({"details", "summary"})
    else:
        for tag in ("details", "summary"):
            if tag not in block_elements:
                block_elements.append(tag)
    body = renderer.convert(normalized)
    return normalized, body


def markdown_viewer_light_css() -> str:
    return _VIEWER_LIGHT_CSS


def markdown_viewer_bootstrap_script() -> str:
    return _VIEWER_ENHANCEMENT_SCRIPT


def render_markdown_viewer_document(
    content: str,
    *,
    base_url: str | None = None,
    katex_asset_root: str | None = None,
) -> RenderedMarkdownViewerDocument:
    normalized, body_html = _render_markdown_body(content)
    base_tag = f'<base href="{html.escape(base_url, quote=True)}">' if base_url else ""
    head_html = (
        "<meta charset='UTF-8'>"
        f"{base_tag}"
        f"<style>{markdown_viewer_light_css()}</style>"
        f"{katex_assets(asset_root=katex_asset_root)}"
        f"<script>{markdown_viewer_bootstrap_script()}</script>"
    )
    full_html = (
        "<!DOCTYPE html>"
        "<html><head>"
        f"{head_html}"
        "</head><body>"
        f"<div class='markdown-rendered'>{body_html}</div>"
        "<script>window.ExocortexMarkdownViewer.run('.markdown-rendered');</script>"
        "</body></html>"
    )
    return RenderedMarkdownViewerDocument(
        normalized_markdown=normalized,
        body_html=body_html,
        head_html=head_html,
        full_html=full_html,
    )


def anki_markdown_viewer_assets() -> AnkiMarkdownViewerAssets:
    katex_dir = katex_asset_dir()
    if katex_dir is None:
        raise FileNotFoundError("KaTeX assets not found under web/public/vendor/katex or web/dist/vendor/katex.")

    katex_css_path = katex_dir / "katex.min.css"
    rewritten_katex_css = _KATEX_CSS_URL_PATTERN.sub(r"url(\1\2\1)", katex_css_path.read_text(encoding="utf-8"))

    media_files = list(katex_dir.glob("fonts/*"))
    media_files.extend(katex_dir / relative_path for relative_path in _KATEX_MEDIA_FILES)

    scripts_html = (
        "<script src=\"katex.min.js\"></script>"
        "<script src=\"copy-tex.min.js\"></script>"
        "<script src=\"auto-render.min.js\"></script>"
        f"<script>{markdown_viewer_bootstrap_script()}</script>"
        "<script>window.ExocortexMarkdownViewer.run('.markdown-rendered');</script>"
    )
    return AnkiMarkdownViewerAssets(
        css=f"{rewritten_katex_css}\n\n{markdown_viewer_light_css()}",
        scripts_html=scripts_html,
        media_files=tuple(media_files),
    )


__all__ = [
    "AnkiMarkdownViewerAssets",
    "RenderedMarkdownViewerDocument",
    "anki_markdown_viewer_assets",
    "markdown_viewer_bootstrap_script",
    "markdown_viewer_light_css",
    "render_markdown_viewer_document",
]
