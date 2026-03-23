import type { ChangeEvent, ReactNode } from "react";

interface PdfPaneToolbarProps {
  pageCount: number;
  currentPage: number;
  zoom: number;
  toolbarSlot?: ReactNode;
  onPageInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onZoomOut: () => void;
  onZoomIn: () => void;
  onZoomReset: () => void;
  onRefresh: () => void;
}

export function PdfPaneToolbar({
  pageCount,
  currentPage,
  zoom,
  toolbarSlot,
  onPageInputChange,
  onZoomOut,
  onZoomIn,
  onZoomReset,
  onRefresh,
}: PdfPaneToolbarProps) {
  return (
    <header className="pdf-pane__toolbar">
      <div className="pdf-pane__toolbar-group">
        <span className="pdf-pane__label">Page</span>
        <input
          className="pdf-pane__page-input"
          disabled={!pageCount}
          max={pageCount || 1}
          min={1}
          onChange={onPageInputChange}
          type="number"
          value={pageCount ? currentPage : 1}
        />
        <span className="pdf-pane__meta">{pageCount ? `/ ${pageCount}` : "/ -"}</span>
      </div>
      <div className="pdf-pane__toolbar-group">
        <button
          className="pdf-pane__button"
          onClick={onZoomOut}
          type="button"
        >
          -
        </button>
        <span className="pdf-pane__meta">{Math.round(zoom * 100)}%</span>
        <button
          className="pdf-pane__button"
          onClick={onZoomIn}
          type="button"
        >
          +
        </button>
        <button
          className="pdf-pane__button pdf-pane__button--secondary"
          onClick={onZoomReset}
          type="button"
        >
          Reset
        </button>
      </div>
      {toolbarSlot ? (
        <div className="pdf-pane__toolbar-group pdf-pane__toolbar-group--spacer">
          {toolbarSlot}
        </div>
      ) : null}
      <button
        className="pdf-pane__button pdf-pane__button--secondary pdf-pane__button--refresh"
        onClick={onRefresh}
        type="button"
      >
        Refresh
      </button>
    </header>
  );
}
