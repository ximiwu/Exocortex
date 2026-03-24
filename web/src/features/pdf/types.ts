import type { AppMode, AssetState, PdfMetadata as WirePdfMetadata, Rect } from "../../generated/contracts";
import type {
  PdfPageTextBoxes as AppPdfPageTextBoxes,
  PdfSearchMatch as AppPdfSearchMatch,
  PdfSearchResponse as AppPdfSearchResponse,
  PdfTextBox as AppPdfTextBox,
} from "../../app/api/types";

export type { AppMode };
export type PdfRect = Rect;

export interface NormalizedPageRect {
  x: number;
  y: number;
  width: number;
  height: number;
}

type AssetBlockRecord = AssetState["blocks"][number];
export type PdfBlockRecord = Omit<AssetBlockRecord, "rect" | "fractionRect"> & {
  rect?: PdfRect;
  fractionRect?: PdfRect;
};
export type PdfGroupRecord = AssetState["groups"][number];
export type PdfAssetSummary = AssetState["asset"];
export type PdfUiState = AssetState["uiState"];
export type PdfAssetState = AssetState;
export type PdfTextBox = AppPdfTextBox;
export type PdfPageTextBoxes = AppPdfPageTextBoxes;
export type PdfSearchMatch = AppPdfSearchMatch;
export type PdfSearchResponse = AppPdfSearchResponse;

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
  fractionRect: PdfRect;
}
