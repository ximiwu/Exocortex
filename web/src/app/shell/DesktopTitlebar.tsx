import type { ThemeMode } from "../types";
import { ThemeToggleIcon } from "./ThemeToggleIcon";

interface DesktopTitlebarProps {
  theme: ThemeMode;
  selectedAssetName: string | null;
  isMaximized: boolean;
  onToggleTheme: () => void;
  onMinimize: () => void;
  onToggleMaximize: () => void;
  onClose: () => void;
}

export function DesktopTitlebar({
  theme,
  selectedAssetName,
  isMaximized,
  onToggleTheme,
  onMinimize,
  onToggleMaximize,
  onClose,
}: DesktopTitlebarProps) {
  return (
    <header className="shell__desktopTitlebar">
      <div className="shell__desktopDragRegion pywebview-drag-region">
        <div className="shell__desktopBrand">Exocortex</div>
        <div className="shell__desktopMeta">
          {selectedAssetName ?? "Desktop shell"}
        </div>
      </div>

      <div className="shell__desktopActions">
        <button
          className="shell__themeToggle shell__themeToggle--titlebar"
          type="button"
          onClick={onToggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
        >
          <ThemeToggleIcon theme={theme} />
        </button>

        <button
          className="shell__windowControl"
          type="button"
          onClick={onMinimize}
          aria-label="Minimize window"
          title="Minimize"
        >
          <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
            <path d="M3 8.5h10" fill="none" stroke="currentColor" strokeLinecap="round" strokeWidth="1.5" />
          </svg>
        </button>

        <button
          className="shell__windowControl"
          type="button"
          onClick={onToggleMaximize}
          aria-label={isMaximized ? "Restore window" : "Maximize window"}
          title={isMaximized ? "Restore" : "Maximize"}
        >
          {isMaximized ? (
            <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
              <path
                d="M5 3.5h6.5a1 1 0 0 1 1 1V11M4.5 5H11a1 1 0 0 1 1 1v6H5.5a1 1 0 0 1-1-1z"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.2"
              />
            </svg>
          ) : (
            <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
              <rect
                x="3.5"
                y="3.5"
                width="9"
                height="9"
                rx="1"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="1.2"
              />
            </svg>
          )}
        </button>

        <button
          className="shell__windowControl shell__windowControl--close"
          type="button"
          onClick={onClose}
          aria-label="Close window"
          title="Close"
        >
          <svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true">
            <path
              d="m4 4 8 8M12 4l-8 8"
              fill="none"
              stroke="currentColor"
              strokeLinecap="round"
              strokeWidth="1.5"
            />
          </svg>
        </button>
      </div>
    </header>
  );
}
