import { MarkdownTab } from "../../app/types";

interface MarkdownTabStripProps {
  tabs: MarkdownTab[];
  currentPath: string | null;
  onActivate: (path: string) => void;
  onClose: (path: string) => void;
}

export function MarkdownTabStrip({ tabs, currentPath, onActivate, onClose }: MarkdownTabStripProps) {
  return (
    <div className="workspace__tabStrip">
      {tabs.map((tab) => {
        const isActive = tab.path === currentPath;
        return (
          <div className={`workspace__tab${isActive ? " is-active" : ""}`} key={tab.path}>
            <button className="workspace__tabButton" type="button" onClick={() => onActivate(tab.path)}>
              <span className="workspace__tabTitle">{tab.title}</span>
              <span className="workspace__tabMeta">{tab.kind}</span>
            </button>

            <button
              className="workspace__tabClose"
              type="button"
              aria-label={`Close ${tab.title}`}
              onClick={(event) => {
                event.stopPropagation();
                onClose(tab.path);
              }}
            >
              ×
            </button>
          </div>
        );
      })}
    </div>
  );
}
