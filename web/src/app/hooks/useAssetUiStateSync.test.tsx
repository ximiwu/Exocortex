import { act, cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ExocortexApi } from "../api/exocortexApi";
import type { AssetState, AssetSummary } from "../types";
import { useAppStore } from "../store/appStore";
import type { AppStoreState } from "../store/appStore";
import { useAssetUiStateSync } from "./useAssetUiStateSync";

const INITIAL_STORE_STATE = useAppStore.getState();

function resetStore(overrides: Partial<AppStoreState> = {}) {
  useAppStore.setState(
    {
      ...INITIAL_STORE_STATE,
      selectedAssetName: null,
      currentMarkdownPath: null,
      openTabs: [],
      ...overrides,
    },
    true,
  );
}

function createAssetSummary(name: string): AssetSummary {
  return {
    name,
    pageCount: 8,
    hasReferences: false,
    hasBlocks: false,
  };
}

function createAssetState(
  assetName: string,
  uiState: Partial<AssetState["uiState"]> = {},
): AssetState {
  return {
    asset: {
      name: assetName,
      pageCount: 8,
      pdfPath: `${assetName}/raw.pdf`,
    },
    references: [],
    blocks: [],
    mergeOrder: [],
    disabledContentItemIndexes: [],
    nextBlockId: 1,
    groups: [],
    uiState: {
      currentPage: 1,
      zoom: 1,
      pdfScrollFraction: 0,
      pdfScrollLeftFraction: 0,
      currentMarkdownPath: null,
      openMarkdownPaths: [],
      sidebarCollapsed: false,
      sidebarCollapsedNodeIds: [],
      markdownScrollFractions: {},
      sidebarWidthRatio: 0.2,
      rightRailWidthRatio: 0.25,
      ...uiState,
    },
  };
}

function createApi(): Pick<ExocortexApi, "mode" | "assets"> {
  const assetState = createAssetState("asset-a");
  return {
    mode: "mock",
    assets: {
      list: vi.fn(async () => []),
      getState: vi.fn(async () => assetState),
      updateUiState: vi.fn(async () => assetState),
      importAsset: vi.fn(async () => {
        throw new Error("not implemented");
      }),
      deleteAsset: vi.fn(async () => undefined),
      revealAsset: vi.fn(async () => undefined),
    },
  };
}

function AssetUiStateSyncHarness({
  api,
  assets,
  assetState,
}: {
  api: Pick<ExocortexApi, "mode" | "assets">;
  assets: AssetSummary[];
  assetState: AssetState | null;
}) {
  useAssetUiStateSync({
    api,
    assets,
    assetState,
  });
  return null;
}

describe("useAssetUiStateSync", () => {
  afterEach(() => {
    cleanup();
    useAppStore.setState(INITIAL_STORE_STATE, true);
    vi.restoreAllMocks();
  });

  it("preserves local markdown scroll fractions when remote ui state is missing or stale", async () => {
    const assetName = "asset-a";
    const currentPath = "group_data/1/img_explainer_data/enhanced.md";
    const otherPath = "group_data/1/img_explainer_data/notes.md";
    const remoteOnlyPath = "group_data/1/img_explainer_data/reference.md";

    resetStore({
      selectedAssetName: assetName,
      currentMarkdownPath: currentPath,
      openTabs: [
        {
          assetName,
          path: currentPath,
          title: "enhanced.md",
          kind: "markdown",
        },
        {
          assetName,
          path: otherPath,
          title: "notes.md",
          kind: "markdown",
        },
      ],
      markdownScrollFractionsByAsset: {
        [assetName]: {
          [currentPath]: 0.61,
          [otherPath]: 0.27,
        },
      },
    });

    await act(async () => {
      render(
        <AssetUiStateSyncHarness
          api={createApi()}
          assets={[createAssetSummary(assetName)]}
          assetState={createAssetState(assetName, {
            markdownScrollFractions: {
              [currentPath]: 0.12,
              [remoteOnlyPath]: 0.9,
            },
          })}
        />,
      );
    });

    await waitFor(() => {
      expect(useAppStore.getState().markdownScrollFractionsByAsset[assetName]).toEqual({
        [currentPath]: 0.61,
        [otherPath]: 0.27,
        [remoteOnlyPath]: 0.9,
      });
    });
  });
});
