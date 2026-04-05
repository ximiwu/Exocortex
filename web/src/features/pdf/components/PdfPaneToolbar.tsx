import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type KeyboardEvent,
  type ReactNode,
} from "react";

interface PdfPaneToolbarProps {
  pageCount: number;
  currentPage: number;
  zoom: number;
  toolbarSlot?: ReactNode;
  searchQuery: string;
  searchStatus: string;
  searchBusy: boolean;
  searchError: boolean;
  canNavigateSearchUp: boolean;
  canNavigateSearchDown: boolean;
  onPageInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSearchInputChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onSearchInputKeyDown: (event: KeyboardEvent<HTMLInputElement>) => void;
  onSearchUp: () => void;
  onSearchDown: () => void;
  onZoomOut: () => void;
  onZoomIn: () => void;
  onZoomReset: () => void;
  onZoomCommit: (zoom: number) => void;
  onRefresh: () => void;
}

export function PdfPaneToolbar({
  pageCount,
  currentPage,
  zoom,
  toolbarSlot,
  searchQuery,
  searchStatus,
  searchBusy,
  searchError,
  canNavigateSearchUp,
  canNavigateSearchDown,
  onPageInputChange,
  onSearchInputChange,
  onSearchInputKeyDown,
  onSearchUp,
  onSearchDown,
  onZoomOut,
  onZoomIn,
  onZoomReset,
  onZoomCommit,
  onRefresh,
}: PdfPaneToolbarProps) {
  const [zoomEditing, setZoomEditing] = useState(false);
  const [zoomInputValue, setZoomInputValue] = useState(formatZoomInputValue(zoom));
  const zoomInputRef = useRef<HTMLInputElement | null>(null);
  const ignoreNextZoomBlurRef = useRef(false);

  useEffect(() => {
    if (zoomEditing) {
      return;
    }
    setZoomInputValue(formatZoomInputValue(zoom));
  }, [zoom, zoomEditing]);

  useEffect(() => {
    if (!zoomEditing || !zoomInputRef.current) {
      return;
    }

    zoomInputRef.current.focus();
    zoomInputRef.current.select();
  }, [zoomEditing]);

  function beginZoomEdit(): void {
    ignoreNextZoomBlurRef.current = false;
    setZoomInputValue(formatZoomInputValue(zoom));
    setZoomEditing(true);
  }

  function cancelZoomEdit(): void {
    ignoreNextZoomBlurRef.current = true;
    setZoomEditing(false);
    setZoomInputValue(formatZoomInputValue(zoom));
  }

  function commitZoomEdit(): void {
    const nextZoom = parseZoomInputValue(zoomInputValue);
    setZoomEditing(false);
    setZoomInputValue(formatZoomInputValue(zoom));

    if (nextZoom == null || Math.abs(nextZoom - zoom) < 1e-6) {
      return;
    }

    onZoomCommit(nextZoom);
  }

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
        {zoomEditing ? (
          <input
            aria-label="Zoom percentage"
            className="pdf-pane__zoom-input"
            inputMode="decimal"
            onBlur={() => {
              if (ignoreNextZoomBlurRef.current) {
                ignoreNextZoomBlurRef.current = false;
                return;
              }
              commitZoomEdit();
            }}
            onChange={(event) => {
              setZoomInputValue(event.target.value);
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                ignoreNextZoomBlurRef.current = true;
                commitZoomEdit();
                return;
              }
              if (event.key === "Escape") {
                event.preventDefault();
                cancelZoomEdit();
              }
            }}
            ref={zoomInputRef}
            type="text"
            value={zoomInputValue}
          />
        ) : (
          <button
            className="pdf-pane__zoom-button"
            onClick={beginZoomEdit}
            title="Edit zoom percentage"
            type="button"
          >
            {formatZoomDisplay(zoom)}
          </button>
        )}
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
      <div className="pdf-pane__toolbar-group pdf-pane__toolbar-group--search">
        <label className="pdf-pane__searchField">
          <span className="pdf-pane__searchLabel">Search</span>
          <input
            aria-label="Search PDF content"
            autoComplete="off"
            className="pdf-pane__searchInput"
            onChange={onSearchInputChange}
            onKeyDown={onSearchInputKeyDown}
            placeholder="Find in PDF"
            spellCheck={false}
            type="text"
            value={searchQuery}
          />
        </label>
        <button
          aria-label="Find previous match"
          className="pdf-pane__button pdf-pane__button--search"
          disabled={!canNavigateSearchUp}
          onClick={onSearchUp}
          type="button"
        >
          ^
        </button>
        <button
          aria-label="Find next match"
          className="pdf-pane__button pdf-pane__button--search"
          disabled={!canNavigateSearchDown}
          onClick={onSearchDown}
          type="button"
        >
          v
        </button>
        <span
          aria-live="polite"
          className={joinClasses(
            "pdf-pane__searchStatus",
            searchBusy ? "pdf-pane__searchStatus--busy" : undefined,
            searchError ? "pdf-pane__searchStatus--error" : undefined,
          )}
        >
          {searchStatus}
        </span>
      </div>
      <div className="pdf-pane__toolbar-actions">
        {toolbarSlot ? (
          <div className="pdf-pane__toolbar-group">
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
      </div>
    </header>
  );
}

function joinClasses(...values: Array<string | undefined>): string {
  return values.filter(Boolean).join(" ");
}

function formatZoomDisplay(zoom: number): string {
  return `${formatZoomInputValue(zoom)}%`;
}

function formatZoomInputValue(zoom: number): string {
  const percentage = zoom * 100;
  const rounded = Number(percentage.toFixed(2));
  return Number.isFinite(rounded) ? rounded.toString() : "100";
}

function parseZoomInputValue(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }

  const normalized = trimmed.endsWith("%") ? trimmed.slice(0, -1).trim() : trimmed;
  if (!normalized) {
    return null;
  }

  const parsed = Number(normalized);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null;
  }

  return parsed / 100;
}
