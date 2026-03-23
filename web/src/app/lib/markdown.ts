import katex from "katex";
import renderMathInElement from "katex/contrib/auto-render";
import "katex/contrib/copy-tex";
import "katex/dist/katex.min.css";

function ensureNoteContainers(root: HTMLElement) {
  root.querySelectorAll("details").forEach((element) => {
    const detail = element as HTMLDetailsElement;
    if (detail.classList.contains("note") && !detail.classList.contains("note-container")) {
      detail.classList.add("note-container");
    }

    if (!detail.classList.contains("note-container")) {
      return;
    }

    const summary = detail.querySelector(":scope > summary");
    const existingContent = detail.querySelector(":scope > .note-content");
    if (existingContent) {
      return;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "note-content";

    Array.from(detail.childNodes).forEach((child) => {
      if (summary && child === summary) {
        return;
      }
      wrapper.appendChild(child);
    });

    detail.appendChild(wrapper);
  });
}

function createDetailsTabGroup(detailsList: HTMLDetailsElement[]) {
  if (detailsList.length < 2) {
    return;
  }

  const parent = detailsList[0].parentElement;
  if (!parent) {
    return;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "markdown-tab-group is-expanded";

  const header = document.createElement("div");
  header.className = "markdown-tab-group__tabs";

  const content = document.createElement("div");
  content.className = "markdown-tab-group__content";

  parent.insertBefore(wrapper, detailsList[0]);
  wrapper.appendChild(header);
  wrapper.appendChild(content);

  detailsList.forEach((detail, index) => {
    const summary = detail.querySelector(":scope > summary");
    const title = summary?.textContent?.trim() || `Tab ${index + 1}`;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "markdown-tab-group__tab";
    button.textContent = title;

    const pane = document.createElement("div");
    pane.className = "markdown-tab-group__pane";

    detail.open = true;
    pane.appendChild(detail);
    content.appendChild(pane);
    header.appendChild(button);

    button.addEventListener("click", () => {
      const isActive = button.classList.contains("is-active");

      header.querySelectorAll(".markdown-tab-group__tab").forEach((tab) => {
        tab.classList.remove("is-active");
      });
      content.querySelectorAll(".markdown-tab-group__pane").forEach((currentPane) => {
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

function buildDetailsTabGroups(root: HTMLElement) {
  const candidateParents = new Set<HTMLElement>();
  root.querySelectorAll("details").forEach((detail) => {
    const parent = detail.parentElement;
    if (!parent) {
      return;
    }
    if (parent.classList.contains("markdown-tab-group__pane")) {
      return;
    }
    candidateParents.add(parent as HTMLElement);
  });

  candidateParents.forEach((parent) => {
    const currentRun: HTMLDetailsElement[] = [];

    const flush = () => {
      if (currentRun.length >= 2) {
        createDetailsTabGroup([...currentRun]);
      }
      currentRun.length = 0;
    };

    Array.from(parent.childNodes).forEach((node) => {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.textContent?.trim()) {
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

function unwrapMathDelimiters(value: string) {
  const text = value.trim();
  const delimiterPairs: Array<{ left: string; right: string; displayMode: boolean }> = [
    { left: "\\[", right: "\\]", displayMode: true },
    { left: "$$", right: "$$", displayMode: true },
    { left: "\\(", right: "\\)", displayMode: false },
    { left: "$", right: "$", displayMode: false },
  ];

  for (const delimiter of delimiterPairs) {
    if (text.startsWith(delimiter.left) && text.endsWith(delimiter.right)) {
      return {
        tex: text.slice(delimiter.left.length, text.length - delimiter.right.length).trim(),
        displayMode: delimiter.displayMode,
      };
    }
  }

  return { tex: text, displayMode: false };
}

function renderArithmatexNodes(root: HTMLElement) {
  root.querySelectorAll<HTMLElement>(".arithmatex").forEach((element) => {
    if (element.dataset.mathRendered === "true") {
      return;
    }

    const source = unwrapMathDelimiters(element.textContent ?? "");
    if (!source.tex) {
      element.dataset.mathRendered = "true";
      return;
    }

    try {
      katex.render(source.tex, element, {
        displayMode: source.displayMode,
        throwOnError: false,
        strict: "ignore",
      });
      element.dataset.mathRendered = "true";
    } catch {
      // Leave raw math markup in place if a specific formula is malformed.
    }
  });
}

export function enhanceMathContent(root: HTMLElement) {
  try {
    const hasArithmatexNodes = root.querySelector(".arithmatex") !== null;
    if (hasArithmatexNodes) {
      renderArithmatexNodes(root);
      return;
    }

    renderMathInElement(root, {
      delimiters: [
        { left: "$$", right: "$$", display: true },
        { left: "\\[", right: "\\]", display: true },
        { left: "$", right: "$", display: false },
        { left: "\\(", right: "\\)", display: false },
      ],
      throwOnError: false,
    });
  } catch {
    // Leave raw math markup in place if KaTeX cannot parse a span.
  }
}

export function enhanceMarkdownContent(root: HTMLElement) {
  ensureNoteContainers(root);
  buildDetailsTabGroups(root);
  enhanceMathContent(root);
}
