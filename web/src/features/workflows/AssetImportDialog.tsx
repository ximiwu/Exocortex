import { type FormEvent, useEffect, useState } from "react";
import type { ImportAssetInput } from "../../app/api/types";
import { Modal } from "../shared/Modal";

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
  const [markdownFile, setMarkdownFile] = useState<File | null>(null);
  const [contentListFile, setContentListFile] = useState<File | null>(null);
  const [assetName, setAssetName] = useState("");
  const [assetSubfolder, setAssetSubfolder] = useState("");
  const [assetNameEdited, setAssetNameEdited] = useState(false);

  useEffect(() => {
    if (!open) {
      return;
    }

    setSourceFile(null);
    setMarkdownFile(null);
    setContentListFile(null);
    setAssetName("");
    setAssetSubfolder("");
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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!sourceFile || !markdownFile || !contentListFile || !assetName.trim()) {
      return;
    }

    await onSubmit({
      sourceFile,
      markdownFile,
      contentListFile,
      assetName: assetName.trim(),
      assetSubfolder: assetSubfolder.trim(),
    });
  }

  return (
    <Modal open={open} wide>
      <form onSubmit={handleSubmit}>
        <p className="section-kicker">New Asset</p>
        <h2>Browser import flow</h2>
        <p className="modal-copy">
          Upload the source PDF, required markdown, and required content list file, optionally provide a subfolder, and kick off asset initialization from the browser.
        </p>
        {errorMessage ? <div className="workflow-formError">{errorMessage}</div> : null}

        <label className="form-field">
          <span>source pdf *</span>
          <input
            type="file"
            accept=".pdf,application/pdf"
            onChange={(event) => {
              setSourceFile(event.currentTarget.files?.[0] ?? null);
            }}
            disabled={submitting}
          />
        </label>
        <p className="workflow-formHint">
          Required. The uploaded PDF remains the asset's raw source file.
        </p>

        <label className="form-field">
          <span>markdown file *</span>
          <input
            type="file"
            accept=".md"
            onChange={(event) => {
              setMarkdownFile(event.currentTarget.files?.[0] ?? null);
            }}
            disabled={submitting}
          />
        </label>
        <p className="workflow-formHint">
          Required. The uploaded markdown is used on top of the existing initialization flow.
        </p>

        <label className="form-field">
          <span>content list json *</span>
          <input
            type="file"
            accept=".json,application/json"
            onChange={(event) => {
              setContentListFile(event.currentTarget.files?.[0] ?? null);
            }}
            disabled={submitting}
          />
        </label>
        <p className="workflow-formHint">
          Required. This file will be saved to the asset directory as <code>content_list.json</code>.
        </p>

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

        <div className="hint-grid">
          <p>pdf: {sourceFile?.name ?? "none selected"}</p>
          <p>markdown: {markdownFile?.name ?? "none selected"}</p>
          <p>content list: {contentListFile?.name ?? "none selected"}</p>
        </div>

        <div className="modal-actions">
          <button className="ghost-button" type="button" onClick={onClose} disabled={submitting}>
            cancel
          </button>
          <button
            className="primary-button"
            type="submit"
            disabled={!sourceFile || !markdownFile || !contentListFile || !assetName.trim() || submitting}
          >
            {submitting ? "starting..." : "import asset"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
