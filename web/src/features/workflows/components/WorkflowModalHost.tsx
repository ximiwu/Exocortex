import type { ImportAssetInput } from "../../../app/api/types";
import { TaskCenter } from "../../tasks/TaskCenter";
import { AssetImportDialog } from "../AssetImportDialog";
import { ConfirmationDialog } from "../ConfirmationDialog";
import { Modal } from "../../shared/Modal";
import type {
  CompressPreviewState,
  ConfirmationState,
} from "../controllers/types";

interface WorkflowModalHostProps {
  activeTaskPanel: boolean;
  importDialogOpen: boolean;
  importSubmitting: boolean;
  importError: string | null;
  confirmation: ConfirmationState | null;
  confirmationBusy: boolean;
  compressPreview: CompressPreviewState | null;
  onCloseTaskPanel: () => void;
  onCloseImportDialog: () => void;
  onImportSubmit: (payload: ImportAssetInput) => Promise<void>;
  onCancelConfirmation: () => void;
  onConfirmAction: () => Promise<void>;
  onCloseCompressPreview: () => void;
}

export function WorkflowModalHost({
  activeTaskPanel,
  importDialogOpen,
  importSubmitting,
  importError,
  confirmation,
  confirmationBusy,
  compressPreview,
  onCloseTaskPanel,
  onCloseImportDialog,
  onImportSubmit,
  onCancelConfirmation,
  onConfirmAction,
  onCloseCompressPreview,
}: WorkflowModalHostProps) {
  return (
    <>
      {activeTaskPanel ? (
        <Modal open={activeTaskPanel} wide className="workflow-modalCard">
          <TaskCenter
            visible={activeTaskPanel}
            onClose={onCloseTaskPanel}
            variant="embedded"
          />
        </Modal>
      ) : null}

      <AssetImportDialog
        open={importDialogOpen}
        submitting={importSubmitting}
        errorMessage={importError}
        onClose={onCloseImportDialog}
        onSubmit={onImportSubmit}
      />

      <ConfirmationDialog
        open={Boolean(confirmation)}
        title={confirmation?.title ?? ""}
        description={confirmation?.description ?? ""}
        confirmLabel={confirmation?.confirmLabel ?? "confirm"}
        tone={confirmation?.tone}
        busy={confirmationBusy}
        onCancel={onCancelConfirmation}
        onConfirm={() => {
          void onConfirmAction();
        }}
      />

      {compressPreview ? (
        <Modal open={Boolean(compressPreview)} wide>
          <p className="section-kicker">Compress Preview</p>
          <h2>Current selection preview</h2>
          <p className="modal-copy">
            {compressPreview.width && compressPreview.height
              ? `Rendered preview at ${compressPreview.width} x ${compressPreview.height}.`
              : "Rendered preview for the current compress selection."}
          </p>
          <img
            alt="Compressed preview"
            src={compressPreview.dataUrl}
            style={{ width: "100%", borderRadius: "16px", border: "1px solid rgba(15, 23, 42, 0.12)" }}
          />
          <div className="modal-actions">
            <button className="primary-button" type="button" onClick={onCloseCompressPreview}>
              close
            </button>
          </div>
        </Modal>
      ) : null}
    </>
  );
}
