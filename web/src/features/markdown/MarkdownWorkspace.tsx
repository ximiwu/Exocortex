import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { useExocortexApi } from "../../app/api/ExocortexApiContext";
import { queryKeys } from "../../app/api/exocortexApi";
import { MarkdownTab } from "../../app/types";
import { useAppStore } from "../../app/store/appStore";
import { MarkdownDocument } from "./MarkdownDocument";

interface MarkdownWorkspaceProps {
  selectedAssetName: string | null;
}

const EMPTY_TABS: MarkdownTab[] = [];

export function MarkdownWorkspace({ selectedAssetName }: MarkdownWorkspaceProps) {
  const api = useExocortexApi();
  const allOpenTabs = useAppStore((state) => state.openTabs);
  const currentMarkdownPath = useAppStore((state) => state.currentMarkdownPath);
  const markdownRenderVersionsByAsset = useAppStore((state) => state.markdownRenderVersionsByAsset);
  const setCurrentMarkdownPath = useAppStore((state) => state.setCurrentMarkdownPath);
  const openTabs = selectedAssetName
    ? allOpenTabs.filter((tab) => tab.assetName === selectedAssetName)
    : EMPTY_TABS;

  const currentTab = openTabs.find((tab) => tab.path === currentMarkdownPath) ?? openTabs[0] ?? null;
  const renderVersion =
    selectedAssetName && currentTab?.path
      ? markdownRenderVersionsByAsset[selectedAssetName]?.[currentTab.path] ?? 0
      : 0;

  useEffect(() => {
    if (!currentTab) {
      if (currentMarkdownPath !== null) {
        setCurrentMarkdownPath(null);
      }
      return;
    }

    if (currentTab.path !== currentMarkdownPath) {
      setCurrentMarkdownPath(currentTab.path);
    }
  }, [currentMarkdownPath, currentTab, setCurrentMarkdownPath]);

  const contentQuery = useQuery({
    queryKey: [...queryKeys.markdownContent(selectedAssetName, currentTab?.path ?? null), renderVersion],
    queryFn: () => api.markdown.getContent(selectedAssetName!, currentTab!.path),
    enabled: Boolean(selectedAssetName && currentTab?.path),
  });

  return (
    <section className="workspace">
      <div className="workspace__body">
        <MarkdownDocument
          assetName={selectedAssetName}
          path={currentTab?.path ?? null}
          html={contentQuery.data?.html ?? ""}
          loading={contentQuery.isLoading}
          error={contentQuery.error instanceof Error ? contentQuery.error.message : null}
          renderVersion={renderVersion}
        />
      </div>
    </section>
  );
}
