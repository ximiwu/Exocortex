import { useEffect, useState, type MouseEvent as ReactMouseEvent } from "react";

import { AssetSummary } from "../../app/types";

interface AssetListProps {
  assets: AssetSummary[];
  selectedAssetName: string | null;
  onSelect: (assetName: string) => void;
  onDeleteAsset?: (assetName: string) => void;
}

type AssetPathNode =
  | {
      id: string;
      type: "folder";
      name: string;
      children: AssetPathNode[];
    }
  | {
      id: string;
      type: "asset";
      name: string;
      asset: AssetSummary;
    };

interface MutableFolder {
  id: string;
  name: string;
  folders: Map<string, MutableFolder>;
  assets: AssetSummary[];
}

interface AssetContextMenuState {
  assetName: string;
  x: number;
  y: number;
}

export function AssetList({
  assets,
  selectedAssetName,
  onSelect,
  onDeleteAsset,
}: AssetListProps) {
  const [contextMenu, setContextMenu] = useState<AssetContextMenuState | null>(null);

  useEffect(() => {
    if (!contextMenu) {
      return undefined;
    }

    const closeMenu = () => setContextMenu(null);
    window.addEventListener("click", closeMenu);
    window.addEventListener("scroll", closeMenu, true);
    window.addEventListener("resize", closeMenu);
    window.addEventListener("keydown", closeMenu);
    return () => {
      window.removeEventListener("click", closeMenu);
      window.removeEventListener("scroll", closeMenu, true);
      window.removeEventListener("resize", closeMenu);
      window.removeEventListener("keydown", closeMenu);
    };
  }, [contextMenu]);

  if (!assets.length) {
    return <div className="sidebar__empty">No assets are available yet.</div>;
  }

  const tree = buildAssetPathTree(assets);

  return (
    <div className="sidebar__assetList">
      {tree.map((node) => renderNode(node, 0))}
      {contextMenu ? (
        <div
          className="markdown-contextMenu"
          style={{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }}
          role="menu"
          onClick={(event) => {
            event.stopPropagation();
          }}
          onContextMenu={(event) => event.preventDefault()}
        >
          <button
            className="markdown-contextMenu__item markdown-contextMenu__item--danger"
            type="button"
            role="menuitem"
            onClick={() => {
              setContextMenu(null);
              onDeleteAsset?.(contextMenu.assetName);
            }}
            disabled={!onDeleteAsset}
          >
            delete
          </button>
        </div>
      ) : null}
    </div>
  );

  function renderNode(node: AssetPathNode, depth: number) {
    if (node.type === "folder") {
      return (
        <div className="sidebar__assetFolder" key={node.id}>
          <div className="sidebar__assetFolderLabel" style={{ paddingLeft: `${depth * 16}px` }}>
            {node.name}
          </div>
          <div className="sidebar__assetFolderChildren">
            {node.children.map((child) => renderNode(child, depth + 1))}
          </div>
        </div>
      );
    }

    const isActive = node.asset.name === selectedAssetName;
    return (
      <button
        key={node.id}
        className={`sidebar__assetCard${isActive ? " is-active" : ""}`}
        style={{ marginLeft: `${depth * 16}px` }}
        type="button"
        onClick={() => onSelect(node.asset.name)}
        onContextMenu={(event) => handleAssetContextMenu(event, node.asset.name)}
      >
        <span className="sidebar__assetName">{node.name}</span>
      </button>
    );
  }

  function handleAssetContextMenu(
    event: ReactMouseEvent<HTMLButtonElement>,
    assetName: string,
  ) {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({
      assetName,
      x: Math.max(12, event.clientX),
      y: Math.max(12, event.clientY),
    });
  }
}

function buildAssetPathTree(assets: AssetSummary[]): AssetPathNode[] {
  const root: MutableFolder = {
    id: "root",
    name: "",
    folders: new Map(),
    assets: [],
  };

  for (const asset of [...assets].sort((left, right) => left.name.localeCompare(right.name))) {
    const parts = asset.name.split("/").filter(Boolean);
    if (!parts.length) {
      continue;
    }

    let cursor = root;
    for (let index = 0; index < parts.length - 1; index += 1) {
      const part = parts[index];
      let next = cursor.folders.get(part);
      if (!next) {
        next = {
          id: `${cursor.id}/${part}`,
          name: part,
          folders: new Map(),
          assets: [],
        };
        cursor.folders.set(part, next);
      }
      cursor = next;
    }

    cursor.assets.push(asset);
  }

  return folderChildren(root);
}

function folderChildren(folder: MutableFolder): AssetPathNode[] {
  const folders = Array.from(folder.folders.values())
    .sort((left, right) => left.name.localeCompare(right.name))
    .map((child) => ({
      id: child.id,
      type: "folder" as const,
      name: child.name,
      children: folderChildren(child),
    }));

  const assets = folder.assets
    .slice()
    .sort((left, right) => left.name.localeCompare(right.name))
    .map((asset) => ({
      id: `asset:${asset.name}`,
      type: "asset" as const,
      name: asset.name.split("/").filter(Boolean).at(-1) ?? asset.name,
      asset,
    }));

  return [...folders, ...assets];
}
