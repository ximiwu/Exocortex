import { ApiSource, AssetSummary } from "../../app/types";
import { AssetList } from "./AssetList";

interface AssetPickerOverlayProps {
  assets: AssetSummary[];
  dataSource: ApiSource;
  loading: boolean;
  error: string | null;
  onCreateAsset: () => void;
  onSelect: (assetName: string) => void;
  onDeleteAsset?: (assetName: string) => void;
}

export function AssetPickerOverlay({
  assets,
  dataSource,
  loading,
  error,
  onCreateAsset,
  onSelect,
  onDeleteAsset,
}: AssetPickerOverlayProps) {
  const hasAssets = assets.length > 0;

  return (
    <div className="assetPicker" role="dialog" aria-modal="true" aria-labelledby="asset-picker-title">
      <div className="assetPicker__card">
        {dataSource === "mock" ? <p className="section-kicker">Preview data</p> : null}
        <h2 id="asset-picker-title">Choose how to start</h2>
        <p className="assetPicker__copy">
          Create a new asset from a PDF or Markdown source, or load an existing asset into the workbench.
        </p>
        <div className="assetPicker__split">
          <section className="assetPicker__panel assetPicker__panel--create" aria-labelledby="asset-picker-create-title">
            <p className="section-kicker">New Asset</p>
            <h3 id="asset-picker-create-title">Import from browser</h3>
            <p className="assetPicker__panelCopy">
              Upload a PDF or Markdown file, set the asset path, and start the initialization flow directly from the browser.
            </p>
            <div className="assetPicker__featureList">
              <p>PDF import supports the full init pipeline and optional compress mode.</p>
              <p>Markdown import works for preprocessed content when PDF is not needed.</p>
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
