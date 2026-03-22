import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { useExocortexApi } from "../../app/api/ExocortexApiContext";
import { queryKeys } from "../../app/api/exocortexApi";
import { MarkdownTab, MarkdownTreeNode } from "../../app/types";
import { useAppStore } from "../../app/store/appStore";
import { MarkdownDocument } from "./MarkdownDocument";

interface MarkdownWorkspaceProps {
  selectedAssetName: string | null;
  markdownTree: MarkdownTreeNode[];
}

const EMPTY_TABS: MarkdownTab[] = [];

function countTreeLeaves(nodes: MarkdownTreeNode[]): number {
  return nodes.reduce((count, node) => {
    if (!node.children.length) {
      return count + (node.path ? 1 : 0);
    }
    return count + countTreeLeaves(node.children);
  }, 0);
}

export function MarkdownWorkspace({ selectedAssetName, markdownTree }: MarkdownWorkspaceProps) {
  const api = useExocortexApi();
  const allOpenTabs = useAppStore((state) => state.openTabs);
  const currentMarkdownPath = useAppStore((state) => state.currentMarkdownPath);
  const setCurrentMarkdownPath = useAppStore((state) => state.setCurrentMarkdownPath);
  const openTabs = selectedAssetName
    ? allOpenTabs.filter((tab) => tab.assetName === selectedAssetName)
    : EMPTY_TABS;

  const currentTab = openTabs.find((tab) => tab.path === currentMarkdownPath) ?? openTabs[0] ?? null;

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
    queryKey: queryKeys.markdownContent(selectedAssetName, currentTab?.path ?? null),
    queryFn: () => api.markdown.getContent(selectedAssetName!, currentTab!.path),
    enabled: Boolean(selectedAssetName && currentTab?.path),
  });

  return (
    <section className="workspace">
      <div className="workspace__body">
        <div className="workspace__statusBar">
          <span>{selectedAssetName ?? "No asset selected"}</span>
          <span>
            {countTreeLeaves(markdownTree)} docs · {openTabs.length} open tab{openTabs.length === 1 ? "" : "s"}
          </span>
        </div>

        <MarkdownDocument
          assetName={selectedAssetName}
          path={currentTab?.path ?? null}
          html={contentQuery.data?.html ?? ""}
          loading={contentQuery.isLoading}
          error={contentQuery.error instanceof Error ? contentQuery.error.message : null}
        />
      </div>
    </section>
  );
}
