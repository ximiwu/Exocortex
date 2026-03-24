export const DEFAULT_REFERENCE_DPI = 130;
export const DEFAULT_MIN_DPI = 72;
export const DEFAULT_MAX_DPI = 1200;

export const PDF_MIN_ZOOM = 0.35;
export const PDF_MAX_ZOOM = 3;
export const PDF_ZOOM_STEP = 0.15;
export const PDF_PAGE_GAP = 12;
export const PDF_VIEWPORT_BUFFER = 900;
export const PDF_SCROLL_SETTLE_MS = 140;
export const PDF_PREHEAT_AHEAD_PAGES = 3;
export const PDF_PREHEAT_BEHIND_PAGES = 1;
export const PDF_PREHEAT_FINAL_PAGES = 1;
export const PDF_PREVIEW_SCALE = 0.7;
export const PDF_PAGE_CACHE_RADIUS = 2;
export const PDF_MAX_BITMAP_BYTES_BY_DEVICE_MEMORY = {
  low: 96 * 1024 * 1024,
  medium: 160 * 1024 * 1024,
  high: 256 * 1024 * 1024,
} as const;
export const PDF_MAX_IN_FLIGHT_BYTES_BY_DEVICE_MEMORY = {
  low: 24 * 1024 * 1024,
  medium: 40 * 1024 * 1024,
  high: 64 * 1024 * 1024,
} as const;
export const PDF_SINGLE_PAGE_CAP_BYTES_BY_DEVICE_MEMORY = {
  low: 20 * 1024 * 1024,
  medium: 28 * 1024 * 1024,
  high: 40 * 1024 * 1024,
} as const;
export const PDF_PAGE_TEXT_BOX_STALE_TIME_MS = 5 * 60 * 1000;
export const PDF_TEXT_BOX_CONTAINMENT_EPSILON = 1e-6;
export const PDF_SEARCH_SCROLL_TOP_OFFSET_PX = 48;
export const MIN_SELECTION_SIZE = 4;

export interface OverlayVisualStyle {
  borderColor: string;
  backgroundColor: string;
  borderStyle: "solid" | "dashed";
  borderWidth: number;
  badgeBackground: string;
  badgeColor: string;
  opacity?: number;
}

export const BLOCK_VISUAL_STYLES: Record<
  "default" | "selected" | "hover" | "group" | "groupHover" | "compress",
  OverlayVisualStyle
> = {
  default: {
    borderColor: "rgba(0, 160, 0, 0.78)",
    backgroundColor: "rgba(0, 160, 0, 0.08)",
    borderStyle: "dashed",
    borderWidth: 2,
    badgeBackground: "rgba(0, 160, 0, 0.92)",
    badgeColor: "#f7fff7",
    opacity: 1,
  },
  selected: {
    borderColor: "rgba(30, 144, 255, 0.98)",
    backgroundColor: "rgba(30, 144, 255, 0.14)",
    borderStyle: "solid",
    borderWidth: 3,
    badgeBackground: "rgba(30, 144, 255, 0.98)",
    badgeColor: "#f8fbff",
    opacity: 1,
  },
  hover: {
    borderColor: "rgba(255, 140, 0, 0.98)",
    backgroundColor: "rgba(255, 140, 0, 0.12)",
    borderStyle: "solid",
    borderWidth: 3,
    badgeBackground: "rgba(255, 140, 0, 0.98)",
    badgeColor: "#fff8f0",
    opacity: 1,
  },
  group: {
    borderColor: "rgba(147, 112, 219, 0.82)",
    backgroundColor: "rgba(147, 112, 219, 0.08)",
    borderStyle: "dashed",
    borderWidth: 2,
    badgeBackground: "rgba(147, 112, 219, 0.95)",
    badgeColor: "#fcf9ff",
    opacity: 0.72,
  },
  groupHover: {
    borderColor: "rgba(147, 112, 219, 0.82)",
    backgroundColor: "rgba(147, 112, 219, 0.08)",
    borderStyle: "dashed",
    borderWidth: 2,
    badgeBackground: "rgba(147, 112, 219, 0.95)",
    badgeColor: "#fcf9ff",
    opacity: 0.72,
  },
  compress: {
    borderColor: "rgba(220, 120, 0, 0.92)",
    backgroundColor: "rgba(220, 120, 0, 0.12)",
    borderStyle: "dashed",
    borderWidth: 2,
    badgeBackground: "rgba(220, 120, 0, 0.92)",
    badgeColor: "#fff8ef",
    opacity: 1,
  },
};
