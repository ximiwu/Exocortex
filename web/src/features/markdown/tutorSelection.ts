export function isInlineTutorSelectionEnabled(path: string | null): boolean {
  if (!path) {
    return false;
  }

  if (!/^group_data\/\d+\//i.test(path)) {
    return false;
  }

  return !/\/tutor_data\//i.test(path);
}

export function groupIdxFromMarkdownPath(path: string | null): number | null {
  if (!path) {
    return null;
  }

  const match = path.match(/^group_data\/(\d+)\//i);
  if (!match) {
    return null;
  }

  return Number(match[1]);
}

export function extractTextWithLatex(range: Range): string {
  const fragment = range.cloneContents();

  if (
    !fragment.querySelector(
      ".math-inline, .math-block, [data-math], .arithmatex, .katex, .katex-display",
    )
  ) {
    return range.toString();
  }

  replaceMathWithLatex(fragment);

  const temp = document.createElement("div");
  temp.style.position = "fixed";
  temp.style.left = "-9999px";
  temp.style.opacity = "0";
  temp.style.pointerEvents = "none";
  temp.appendChild(fragment);
  document.body.appendChild(temp);
  const text = temp.innerText ?? temp.textContent ?? "";
  temp.remove();

  return text;
}

function replaceMathWithLatex(root: DocumentFragment): void {
  for (const container of Array.from(root.querySelectorAll<HTMLElement>(".katex-display"))) {
    const latex = latexFromKatexNode(container);
    if (latex) {
      container.replaceWith(document.createTextNode(`$$${latex}$$`));
    }
  }

  for (const container of Array.from(root.querySelectorAll<HTMLElement>(".katex"))) {
    const latex = latexFromKatexNode(container);
    if (latex) {
      container.replaceWith(document.createTextNode(`$${latex}$`));
    }
  }

  for (const container of Array.from(
    root.querySelectorAll<HTMLElement>(".math-inline, .math-block"),
  )) {
    const dataMathEl = container.querySelector<HTMLElement>("[data-math]");
    const latex = dataMathEl?.getAttribute("data-math");
    if (!latex) {
      continue;
    }

    const isBlock = container.classList.contains("math-block");
    container.replaceWith(document.createTextNode(isBlock ? `$$${latex}$$` : `$${latex}$`));
  }

  for (const element of Array.from(root.querySelectorAll<HTMLElement>("[data-math]"))) {
    const latex = element.getAttribute("data-math");
    if (latex) {
      element.replaceWith(document.createTextNode(`$${latex}$`));
    }
  }

  for (const element of Array.from(root.querySelectorAll<HTMLElement>(".arithmatex"))) {
    const source = unwrapMathDelimiters(element.textContent ?? "");
    if (source) {
      element.replaceWith(document.createTextNode(source));
    }
  }
}

function unwrapMathDelimiters(value: string): string {
  const text = value.trim();
  if (!text) {
    return "";
  }

  const delimiterPairs = [
    { left: "\\[", right: "\\]" },
    { left: "$$", right: "$$" },
    { left: "\\(", right: "\\)" },
    { left: "$", right: "$" },
  ];

  for (const delimiter of delimiterPairs) {
    if (text.startsWith(delimiter.left) && text.endsWith(delimiter.right)) {
      const inner = text.slice(delimiter.left.length, text.length - delimiter.right.length).trim();
      if (!inner) {
        return "";
      }
      return delimiter.left.startsWith("\\[") || delimiter.left === "$$"
        ? `$$${inner}$$`
        : `$${inner}$`;
    }
  }

  return text;
}

function latexFromKatexNode(node: HTMLElement): string {
  const annotation =
    node.querySelector<HTMLElement>("annotation[encoding='application/x-tex']") ??
    node.querySelector<HTMLElement>("annotation");

  return annotation?.textContent?.trim() ?? "";
}
