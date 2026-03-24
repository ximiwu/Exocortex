import { memo, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";

import { useExocortexApi } from "../../app/api/ExocortexApiContext";
import { queryKeys } from "../../app/api/exocortexApi";
import { queryClient } from "../../app/lib/queryClient";
import { useAppStore } from "../../app/store/appStore";
import {
  extractTextWithLatex,
  groupIdxFromMarkdownPath,
  isInlineTutorSelectionEnabled,
} from "./tutorSelection";
import { enhanceMarkdownContent } from "./renderAdapter";

interface MarkdownDocumentProps {
  assetName: string | null;
  path: string | null;
  html: string;
  loading: boolean;
  error: string | null;
  renderVersion: number;
}

const RenderedMarkdownContent = memo(function RenderedMarkdownContent({
  html,
  contentRef,
}: {
  html: string;
  contentRef: { current: HTMLDivElement | null };
}) {
  return (
    <div
      className="markdown-rendered"
      ref={contentRef}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
});

function hashHtml(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash.toString(16);
}

export function MarkdownDocument({
  assetName,
  path,
  html,
  loading,
  error,
  renderVersion,
}: MarkdownDocumentProps) {
  const api = useExocortexApi();
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const contentRef = useRef<HTMLDivElement | null>(null);
  const selectionRangeRef = useRef<Range | null>(null);
  const openMarkdownTab = useAppStore((state) => state.openMarkdownTab);
  const requestMarkdownContextMenu = useAppStore((state) => state.requestMarkdownContextMenu);
  const [selectionButton, setSelectionButton] = useState<{
    top: number;
    left: number;
    text: string;
  } | null>(null);
  const [creatingTutorSession, setCreatingTutorSession] = useState(false);
  const contentKey = path ? `${path}:${renderVersion}:${hashHtml(html)}` : "empty";
  const canAskTutorFromSelection = isInlineTutorSelectionEnabled(path);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element || !assetName || !path) {
      return;
    }

    const onScroll = () => {
      const maxScroll = Math.max(0, element.scrollHeight - element.clientHeight);
      const fraction = maxScroll > 0 ? element.scrollTop / maxScroll : 0;
      useAppStore.getState().rememberMarkdownScroll(assetName, path, fraction);
    };

    element.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      element.removeEventListener("scroll", onScroll);
    };
  }, [assetName, path]);

  useLayoutEffect(() => {
    if (!contentRef.current || !html.trim()) {
      return;
    }

    const element = contentRef.current;
    let cancelled = false;
    const timers = new Set<number>();

    const runEnhancement = () => {
      if (cancelled) {
        return;
      }
      enhanceMarkdownContent(element);
    };

    const frame = requestAnimationFrame(runEnhancement);
    for (const delay of [50, 150, 300, 600]) {
      const timer = window.setTimeout(() => {
        timers.delete(timer);
        runEnhancement();
      }, delay);
      timers.add(timer);
    }

    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      for (const timer of timers) {
        window.clearTimeout(timer);
      }
      timers.clear();
    };
  }, [contentKey, html]);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) {
      return;
    }

    const savedFraction =
      assetName && path
        ? useAppStore.getState().markdownScrollFractionsByAsset[assetName]?.[path] ?? 0
        : 0;

    const frame = requestAnimationFrame(() => {
      const maxScroll = Math.max(0, element.scrollHeight - element.clientHeight);
      element.scrollTop = maxScroll > 0 ? savedFraction * maxScroll : 0;
    });

    return () => cancelAnimationFrame(frame);
  }, [assetName, html, path]);

  useEffect(() => {
    selectionRangeRef.current = null;
    setSelectionButton(null);
  }, [assetName, path, html]);

  useEffect(() => {
    if (!assetName || !path || !canAskTutorFromSelection) {
      selectionRangeRef.current = null;
      setSelectionButton(null);
      return;
    }

    const root = contentRef.current;
    if (!root) {
      return;
    }

    const clearSelectionButton = () => {
      selectionRangeRef.current = null;
      setSelectionButton(null);
    };

    const updateSelectionButton = () => {
      const selection = window.getSelection();
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
        clearSelectionButton();
        return;
      }

      const range = selection.getRangeAt(0);
      const commonAncestor =
        range.commonAncestorContainer.nodeType === Node.ELEMENT_NODE
          ? range.commonAncestorContainer
          : range.commonAncestorContainer.parentElement;

      if (!(commonAncestor instanceof Node) || !root.contains(commonAncestor)) {
        clearSelectionButton();
        return;
      }

      const selectedText = extractTextWithLatex(range).trim();
      if (!selectedText) {
        clearSelectionButton();
        return;
      }

      const rangeRect = range.getBoundingClientRect();
      if (!rangeRect.width && !rangeRect.height) {
        clearSelectionButton();
        return;
      }

      selectionRangeRef.current = range.cloneRange();
      const left = Math.min(
        window.innerWidth - 160,
        Math.max(12, rangeRect.left + rangeRect.width / 2 - 68),
      );
      const top = Math.max(12, rangeRect.top - 44);

      setSelectionButton({
        top,
        left,
        text: selectedText,
      });
    };

    const scheduleSelectionUpdate = () => {
      window.setTimeout(updateSelectionButton, 0);
    };

    const handlePointerDown = (event: MouseEvent) => {
      if (!root.contains(event.target as Node)) {
        return;
      }
      clearSelectionButton();
    };

    const handlePointerUp = () => {
      scheduleSelectionUpdate();
    };

    const handleKeyUp = () => {
      scheduleSelectionUpdate();
    };

    const scrollElement = scrollRef.current;

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("mouseup", handlePointerUp);
    document.addEventListener("keyup", handleKeyUp);
    window.addEventListener("resize", scheduleSelectionUpdate);
    scrollElement?.addEventListener("scroll", clearSelectionButton, { passive: true });

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("mouseup", handlePointerUp);
      document.removeEventListener("keyup", handleKeyUp);
      window.removeEventListener("resize", scheduleSelectionUpdate);
      scrollElement?.removeEventListener("scroll", clearSelectionButton);
    };
  }, [assetName, canAskTutorFromSelection, contentKey, html, path]);

  async function handleAskTutorFromSelection() {
    if (!assetName || !path) {
      return;
    }

    const range = selectionRangeRef.current;
    const groupIdx = groupIdxFromMarkdownPath(path);
    const focusMarkdown = (selectionButton?.text ?? (range ? extractTextWithLatex(range) : "")).trim();

    if (!range || groupIdx === null || !focusMarkdown) {
      return;
    }

    try {
      setCreatingTutorSession(true);
      const session = await api.workflows.createTutorSession({ assetName, groupIdx, focusMarkdown });
      await queryClient.invalidateQueries({ queryKey: queryKeys.assetState(assetName) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.markdownTree(assetName) });
      openMarkdownTab({
        assetName,
        path: session.markdownPath,
        title: session.markdownPath.split("/").filter(Boolean).at(-1) ?? "focus.md",
        kind: "markdown",
      });
    } catch (sessionError) {
      console.error("Failed to create tutor session from selection", sessionError);
      window.alert(
        sessionError instanceof Error
          ? sessionError.message
          : "Failed to create tutor session from selection.",
      );
    } finally {
      window.getSelection()?.removeAllRanges();
      selectionRangeRef.current = null;
      setSelectionButton(null);
      setCreatingTutorSession(false);
    }
  }

  function handleMarkdownContextMenu(event: ReactMouseEvent<HTMLElement>) {
    if (!path) {
      return;
    }
    event.preventDefault();
    requestMarkdownContextMenu(event.clientX, event.clientY);
  }

  if (!path) {
    return <div className="workspace__empty">Open a markdown item from the sidebar to begin.</div>;
  }

  if (error) {
    return <div className="workspace__error">{error}</div>;
  }

  return (
    <div className="workspace__document" onContextMenu={handleMarkdownContextMenu}>
      {loading ? <div className="workspace__loading">Loading {path}...</div> : null}
      {selectionButton ? (
        <button
          className="markdown-selectionAction"
          type="button"
          style={{ top: `${selectionButton.top}px`, left: `${selectionButton.left}px` }}
          disabled={creatingTutorSession}
          onMouseDown={(event) => {
            event.preventDefault();
          }}
          onClick={handleAskTutorFromSelection}
        >
          {creatingTutorSession ? "Creating..." : "Ask Tutor"}
        </button>
      ) : null}
      <div className="workspace__documentScroll" ref={scrollRef}>
        <article className="workspace__documentCard">
          <div className="workspace__documentInner">
            <RenderedMarkdownContent key={contentKey} html={html} contentRef={contentRef} />
          </div>
        </article>
      </div>
    </div>
  );
}
