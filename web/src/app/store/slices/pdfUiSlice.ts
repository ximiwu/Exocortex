import type { AppStoreSliceCreator, PdfUiSlice } from "../appStore.types";

export const createPdfUiSlice: AppStoreSliceCreator<PdfUiSlice> = (set) => ({
  currentPage: 1,
  zoom: 1,
  selectedBlockIds: [],
  hoveredBlockId: null,
  hoveredGroupIdx: null,
  appMode: "normal",
  compressSelection: null,
  pdfNavigationRequest: null,
  setCurrentPage: (page) => set({ currentPage: Math.max(1, Math.floor(page || 1)) }),
  setZoom: (zoom) => set({ zoom }),
  setAppMode: (mode) => set({ appMode: mode }),
  setCompressSelection: (selection) => set({ compressSelection: selection }),
  requestPdfNavigation: (assetName, page) =>
    set({
      pdfNavigationRequest: {
        assetName,
        page: Math.max(1, Math.floor(page || 1)),
        nonce: Date.now(),
      },
    }),
  consumePdfNavigationRequest: () => set({ pdfNavigationRequest: null }),
});
