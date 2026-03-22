import type { AppMode, AssetState, PdfMetadata as WirePdfMetadata, Rect } from "../../generated/contracts";

export type { AppMode };
export type PdfRect = Rect;

export interface NormalizedPageRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

export type PdfBlockRecord = AssetState["blocks"][number];
export type PdfGroupRecord = AssetState["groups"][number];
export type PdfAssetSummary = AssetState["asset"];
export type PdfUiState = AssetState["uiState"];
export type PdfAssetState = AssetState;

export interface PdfPageSize {
  width: number;
  height: number;
}

export type PdfMetadata = WirePdfMetadata;

export interface PdfPageLayout {
  pageIndex: number;
  top: number;
  left: number;
  width: number;
  height: number;
  bottom: number;
}

export interface CreateBlockInput {
  pageIndex: number;
  rect: PdfRect;
}
