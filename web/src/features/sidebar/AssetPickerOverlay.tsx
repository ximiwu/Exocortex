import { ApiSource, AssetSummary } from "../../app/types";
import { AssetList } from "./AssetList";

interface AssetPickerOverlayProps {
  assets: AssetSummary[];
  dataSource: ApiSource;
  loading: boolean;
  error: string | null;
  reserveDesktopTitlebarSpace?: boolean;
  onCreateAsset: () => void;
  onSelect: (assetName: string) => void;
  onDeleteAsset?: (assetName: string) => void;
}

export function AssetPickerOverlay({
  assets,
  dataSource,
  loading,
  error,
  reserveDesktopTitlebarSpace = false,
  onCreateAsset,
  onSelect,
  onDeleteAsset,
}: AssetPickerOverlayProps) {
  const hasAssets = assets.length > 0;

  return (
    <div
      className={`assetPicker${reserveDesktopTitlebarSpace ? " assetPicker--reserveDesktopTitlebarSpace" : ""}`}
      role="dialog"
      aria-modal="true"
      aria-labelledby="asset-picker-title"
    >
      <div className="assetPicker__card">
        {dataSource === "mock" ? <p className="section-kicker">Preview data</p> : null}
        <h2 id="asset-picker-title">Choose how to start</h2>
        <p className="assetPicker__copy">
          Create a new asset from its PDF, markdown, and content list, or load an existing asset into the workbench.
        </p>
        <div className="assetPicker__split">
          <section className="assetPicker__panel assetPicker__panel--create" aria-labelledby="asset-picker-create-title">
            <p className="section-kicker">New Asset</p>
            <h3 id="asset-picker-create-title">Import from browser</h3>
            <p className="assetPicker__panelCopy">
              Upload a PDF, a markdown file, and a matching JSON content list, set the asset path, and start the initialization flow directly from the browser.
            </p>
            <div className="assetPicker__featureList">
              <p>PDF stays as the raw source file for every new asset import.</p>
              <p>Markdown is also required and is applied within the existing initialization flow.</p>
              <p>The uploaded JSON file is stored in the asset directory as <code>content_list.json</code>.</p>
              <p>Subfolders let you organize assets as nested paths like <code>physics/paper_1</code>.</p>
            </div>
            <button className="primary-button assetPicker__primaryAction" type="button" onClick={onCreateAsset}>
              new asset
            </button>
          </section>

          <section className="assetPicker__panel assetPicker__panel--load" aria-labelledby="asset-picker-load-title">
            <div className="assetPicker__panelHeader">
              <div>
                <p className="section-kicker">Load Asset</p>
                <h3 id="asset-picker-load-title">Open existing work</h3>
              </div>
              {hasAssets ? <span className="assetPicker__count">{assets.length} available</span> : null}
            </div>
            <div className="assetPicker__content">
              {loading ? <div className="sidebar__empty">Loading assets...</div> : null}
              {error ? <div className="sidebar__error">{error}</div> : null}
              {!loading && !error && hasAssets ? (
                <AssetList
                  assets={assets}
                  selectedAssetName={null}
                  onSelect={onSelect}
                  onDeleteAsset={onDeleteAsset}
                />
              ) : null}
              {!loading && !error && !hasAssets ? (
                <div className="assetPicker__emptyState">
                  <p className="assetPicker__emptyTitle">No assets are available to load yet.</p>
                  <p className="assetPicker__emptyCopy">
                    Use the <code>new asset</code> panel to create the first one.
                  </p>
                </div>
              ) : null}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
