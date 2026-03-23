import { useEffect, useState } from "react";
import {
  GlobalWorkerOptions,
  getDocument,
  type PDFDocumentLoadingTask,
  type PDFDocumentProxy,
} from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

interface PdfJsDocumentState {
  pdfDocument: PDFDocumentProxy | null;
  loading: boolean;
  error: Error | null;
}

const EMPTY_STATE: PdfJsDocumentState = {
  pdfDocument: null,
  loading: false,
  error: null,
};

export function usePdfJsDocument(pdfFileUrl: string | null): PdfJsDocumentState {
  const [state, setState] = useState<PdfJsDocumentState>(EMPTY_STATE);

  useEffect(() => {
    let active = true;
    let loadingTask: PDFDocumentLoadingTask | null = null;
    let resolvedDocument: PDFDocumentProxy | null = null;

    if (!pdfFileUrl) {
      setState(EMPTY_STATE);
      return undefined;
    }

    setState({
      pdfDocument: null,
      loading: true,
      error: null,
    });

    loadingTask = getDocument({
      url: pdfFileUrl,
    });

    void loadingTask.promise.then(
      (nextDocument) => {
        resolvedDocument = nextDocument;
        if (!active) {
          void nextDocument.destroy();
          return;
        }
        setState({
          pdfDocument: nextDocument,
          loading: false,
          error: null,
        });
      },
      (reason: unknown) => {
        if (!active) {
          return;
        }
        setState({
          pdfDocument: null,
          loading: false,
          error: toError(reason),
        });
      },
    );

    return () => {
      active = false;
      if (resolvedDocument) {
        void resolvedDocument.destroy().catch(() => undefined);
        return;
      }
      if (loadingTask) {
        void loadingTask.destroy().catch(() => undefined);
      }
    };
  }, [pdfFileUrl]);

  return state;
}

function toError(reason: unknown): Error {
  return reason instanceof Error ? reason : new Error("Failed to load the PDF document.");
}
