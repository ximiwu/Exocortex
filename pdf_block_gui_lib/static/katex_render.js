(function () {
  function renderArithmatex(root) {
    if (!window.katex) {
      return;
    }

    root.querySelectorAll(".arithmatex").forEach(function (el) {
      let tex = (el.textContent || el.innerText || "").trim();
      let display =
        el.classList.contains("arithmatex-display") ||
        el.tagName.toLowerCase() === "div";
      const prev = el.previousSibling;
      const next = el.nextSibling;

      if (!display && prev && next && prev.textContent && next.textContent) {
        if (prev.textContent.trim() === "$" && next.textContent.trim() === "$") {
          display = true;
          prev.textContent = "";
          next.textContent = "";
        }
      }

      if (tex.startsWith("\\(") && tex.endsWith("\\)")) {
        tex = tex.slice(2, -2);
      } else if (tex.startsWith("\\[") && tex.endsWith("\\]")) {
        tex = tex.slice(2, -2);
        display = true;
      } else if (tex.startsWith("$$") && tex.endsWith("$$")) {
        tex = tex.slice(2, -2);
        display = true;
      }

      try {
        katex.render(tex, el, {
          displayMode: display,
          throwOnError: false,
          strict: "ignore",
        });
      } catch (err) {
        console.error(err);
      }
    });
  }

  function whenKatexReady(cb) {
    let tries = 80;
    (function check() {
      if (window.katex) {
        cb();
        return;
      }
      if (tries-- <= 0) {
        console.warn("KaTeX not available");
        return;
      }
      setTimeout(check, 50);
    })();
  }

  document.addEventListener("DOMContentLoaded", function () {
    whenKatexReady(function () {
      if (typeof renderMathInElement === "function") {
        renderMathInElement(document.body, {
          delimiters: [
            { left: "$$", right: "$$", display: true },
            { left: "\\[", right: "\\]", display: true },
            { left: "$", right: "$", display: false },
            { left: "\\(", right: "\\)", display: false },
          ],
          ignoredClasses: ["katex", "arithmatex"],
          throwOnError: false,
          strict: "ignore",
        });
      }
      renderArithmatex(document);
    });
  });
})();
