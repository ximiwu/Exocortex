import { type FormEvent, useEffect, useState } from "react";
import type { ImportAssetInput } from "../../app/api/types";

interface AssetImportDialogProps {
  open: boolean;
  submitting: boolean;
  errorMessage: string | null;
  onClose(): void;
  onSubmit(payload: ImportAssetInput): Promise<void>;
}

export function AssetImportDialog({
  open,
  submitting,
  errorMessage,
  onClose,
  onSubmit
}: AssetImportDialogProps) {
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [assetName, setAssetName] = useState("");
  const [assetSubfolder, setAssetSubfolder] = useState("");
  const [skipMarkdownFile, setSkipMarkdownFile] = useState<File | null>(null);
  const [compressEnabled, setCompressEnabled] = useState(false);
  const [assetNameEdited, setAssetNameEdited] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }

    setSourceFile(null);
    setAssetName("");
    setAssetSubfolder("");
    setSkipMarkdownFile(null);
    setCompressEnabled(false);
    setAssetNameEdited(false);
  }, [open]);

  useEffect(() => {
    if (!sourceFile || assetNameEdited || assetName.trim()) {
      return;
    }

    const nextName = sourceFile.name.replace(/\.[^.]+$/, "").replace(/\s+/g, "_");
    setAssetName(nextName);
  }, [assetName, assetNameEdited, sourceFile]);

  if (!open) {
    return null;
  }

  const compressSupported = sourceFile?.name.toLowerCase().endsWith(".pdf") ?? false;
  const sourceKindLabel = !sourceFile
    ? "Upload a PDF or Markdown file to begin."
    : compressSupported
      ? "PDF import will run the full initialization flow and can enter compress mode immediately."
      : "Markdown import skips PDF-only actions like compress mode and starts from markdown content.";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sourceFile || !assetName.trim()) {
      return;
    }

    await onSubmit({
      sourceFile,
      assetName: assetName.trim(),
      assetSubfolder: assetSubfolder.trim(),
      skipImg2MdMarkdownFile: skipMarkdownFile,
      compressEnabled: compressSupported && compressEnabled
    });
  }

  return (
    <div className="modal-scrim" role="presentation">
      <form className="modal-card modal-card--wide" onSubmit={handleSubmit}>
        <p className="section-kicker">New Asset</p>
        <h2>Browser import flow</h2>
        <p className="modal-copy">
          Upload a PDF or Markdown source, optionally provide a subfolder, and kick off asset initialization from the browser.
        </p>
        {errorMessage ? <div className="workflow-formError">{errorMessage}</div> : null}

        <label className="form-field">
          <span>source file *</span>
          <input
            type="file"
            accept=".pdf,.md"
            onChange={(event) => {
              const nextSourceFile = event.currentTarget.files?.[0] ?? null;
              setSourceFile(nextSourceFile);
              if (!nextSourceFile?.name.toLowerCase().endsWith(".pdf")) {
                setCompressEnabled(false);
              }
            }}
            disabled={submitting}
          />
        </label>
        <p className="workflow-formHint">{sourceKindLabel}</p>

        <div className="form-grid">
          <label className="form-field">
            <span>asset name *</span>
            <input
              type="text"
              value={assetName}
              onChange={(event) => {
                setAssetName(event.currentTarget.value);
                setAssetNameEdited(true);
              }}
              placeholder="paper_1"
              disabled={submitting}
            />
          </label>
          <label className="form-field">
            <span>asset sub folder</span>
            <input
              type="text"
              value={assetSubfolder}
              onChange={(event) => setAssetSubfolder(event.currentTarget.value)}
              placeholder="physics/semester_2"
              disabled={submitting}
            />
          </label>
        </div>
        <p className="workflow-formHint">
          The final asset path will be <code>{[assetSubfolder.trim(), assetName.trim()].filter(Boolean).join("/") || "asset_name"}</code>.
        </p>

        <label className="form-field">
          <span>replacement markdown for skip img2md</span>
          <input
            type="file"
            accept=".md"
            onChange={(event) => {
              setSkipMarkdownFile(event.currentTarget.files?.[0] ?? null);
            }}
            disabled={submitting}
          />
        </label>
        <p className="workflow-formHint">
          Optional. Provide a prepared markdown file when you want to bypass the image-to-markdown stage.
        </p>

        <label className="checkbox-row">
          <input
            type="checkbox"
            checked={compressEnabled}
            disabled={!compressSupported}
            onChange={(event) => setCompressEnabled(event.currentTarget.checked)}
          />
          <span>compress init flow</span>
        </label>

        <div className="hint-grid">
          <p>source: {sourceFile?.name ?? "none selected"}</p>
          <p>skip markdown: {skipMarkdownFile?.name ?? "not provided"}</p>
          <p>
            compress:{" "}
            {compressSupported
              ? compressEnabled
                ? "the UI will switch into compress mode after import completes."
                : "optional for PDF imports when you want to start selection immediately."
              : "available after PDF imports only."}
          </p>
        </div>

        <div className="modal-actions">
          <button className="ghost-button" type="button" onClick={onClose} disabled={submitting}>
            cancel
          </button>
          <button
            className="primary-button"
            type="submit"
            disabled={!sourceFile || !assetName.trim() || submitting}
          >
            {submitting ? "starting..." : "import asset"}
          </button>
        </div>
      </form>
    </div>
  );
}
