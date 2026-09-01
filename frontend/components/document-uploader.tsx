"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useDropzone } from "react-dropzone";
import {
  CheckCircle2,
  FileText,
  Loader2,
  UploadCloud,
  X,
} from "lucide-react";

import DuplicateDialog from "@/components/duplicate-dialog";
import PortfolioPicker from "@/components/portfolio-picker";
import { apiFetch, wakeBackend } from "@/lib/api";
import { resolveDuplicate, selectPortfolioFile } from "@/lib/documents";
import { formatBytes } from "@/lib/format";
import type {
  EmbeddedFileSummary,
  ExistingDocumentSummary,
  UploadedDocument,
} from "@/types/document";

const ACCEPTED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".png",
  ".jpg",
  ".jpeg",
];

interface DocumentUploaderProps {
  onUploadComplete: (document: UploadedDocument) => void;
}

interface PendingDuplicate {
  documentId: string;
  originalFilename: string;
  existingDocument: ExistingDocumentSummary;
}

interface PendingPortfolio {
  documentId: string;
  files: EmbeddedFileSummary[];
}

export default function DocumentUploader({
  onUploadComplete,
}: DocumentUploaderProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [waking, setWaking] = useState(false);
  const [error, setError] = useState("");
  const [pendingDuplicate, setPendingDuplicate] =
    useState<PendingDuplicate | null>(null);
  const [resolving, setResolving] = useState(false);
  const [pendingPortfolio, setPendingPortfolio] =
    useState<PendingPortfolio | null>(null);
  const [selectingPortfolioFile, setSelectingPortfolioFile] =
    useState(false);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setError("");

    const file = acceptedFiles[0];

    if (!file) return;

    const extension = file.name
      .toLowerCase()
      .slice(file.name.lastIndexOf("."));

    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      setError(
        "Please select a PDF, DOCX, PNG, or JPG document.",
      );
      return;
    }

    setSelectedFile(file);
    setProgress(0);
  }, []);

  const {
    getRootProps,
    getInputProps,
    isDragActive,
  } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        [".docx"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
    },
    multiple: false,
    maxFiles: 1,
  });

  const progressTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearProgressTimer = useCallback(() => {
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
  }, []);

  const startSlowProgress = useCallback(() => {
    clearProgressTimer();
    progressTimerRef.current = setInterval(() => {
      setProgress((current) => (current < 72 ? current + 1 : current));
    }, 2500);
  }, [clearProgressTimer]);

  useEffect(() => () => clearProgressTimer(), [clearProgressTimer]);

  async function uploadDocument() {
    if (!selectedFile) return;

    setUploading(true);
    setError("");
    setWaking(true);
    setProgress(10);
    startSlowProgress();

    const onWakeRetry = () => setWaking(true);

    try {
      await wakeBackend(onWakeRetry);
      setProgress(25);

      const formData = new FormData();
      formData.append("file", selectedFile);

      setProgress(35);

      const result = await apiFetch<UploadedDocument>(
        "/api/documents/upload",
        {
          method: "POST",
          body: formData,
        },
        onWakeRetry,
      );

      clearProgressTimer();
      setProgress(80);

      if (result.status === "portfolio_pending" && result.embedded_files) {
        setPendingPortfolio({
          documentId: result.document_id,
          files: result.embedded_files,
        });
        setProgress(0);
        return;
      }

      if (result.duplicate && result.existing_document) {
        setPendingDuplicate({
          documentId: result.document_id,
          originalFilename: result.original_filename,
          existingDocument: result.existing_document,
        });
        setProgress(0);
        return;
      }

      setProgress(100);

      onUploadComplete(result);
    } catch (uploadError) {
      clearProgressTimer();
      setProgress(0);

      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to upload the document.",
      );
    } finally {
      clearProgressTimer();
      setUploading(false);
      setWaking(false);
    }
  }

  async function handleDuplicateResolution(
    action: "use_existing" | "upload_anyway",
  ) {
    if (!pendingDuplicate) return;

    setResolving(true);
    setError("");

    try {
      const result = await resolveDuplicate(
        pendingDuplicate.documentId,
        action,
        pendingDuplicate.originalFilename,
      );

      setProgress(100);
      setPendingDuplicate(null);
      onUploadComplete(result);
    } catch (resolveError) {
      setError(
        resolveError instanceof Error
          ? resolveError.message
          : "Unable to resolve the duplicate upload.",
      );
    } finally {
      setResolving(false);
    }
  }

  function handleCancelDuplicate() {
    setPendingDuplicate(null);
    setProgress(0);
  }

  async function handlePortfolioSelection(filename: string) {
    if (!pendingPortfolio) return;

    setSelectingPortfolioFile(true);
    setError("");

    try {
      const result = await selectPortfolioFile(
        pendingPortfolio.documentId,
        filename,
      );

      setProgress(100);
      setPendingPortfolio(null);

      if (result.duplicate && result.existing_document) {
        setPendingDuplicate({
          documentId: result.document_id,
          originalFilename: result.original_filename,
          existingDocument: result.existing_document,
        });
        setProgress(0);
        return;
      }

      onUploadComplete(result);
    } catch (selectError) {
      setError(
        selectError instanceof Error
          ? selectError.message
          : "Unable to extract the selected document.",
      );
    } finally {
      setSelectingPortfolioFile(false);
    }
  }

  function handleCancelPortfolio() {
    setPendingPortfolio(null);
    setProgress(0);
  }

  function clearFile() {
    setSelectedFile(null);
    setProgress(0);
    setError("");
  }

  return (
    <div className="editorial-card p-8">
      <div className="mb-6">
        <h2 className="text-xl font-medium tracking-tight text-foreground">
          Upload document
        </h2>

        <p className="mt-2 text-sm leading-6 text-text-secondary">
          Contracts, financial documents, invoices, and scanned agreements.
        </p>
      </div>

      {!selectedFile ? (
        <div
          {...getRootProps()}
          className={[
            "cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition duration-200",
            isDragActive
              ? "border-primary/40 bg-primary-soft/50"
              : "border-border hover:border-primary/25 hover:bg-surface-soft/60",
          ].join(" ")}
        >
          <input {...getInputProps()} />

          <div className="file-icon-wrap mx-auto h-14 w-14">
            <UploadCloud className="h-7 w-7" strokeWidth={1.75} />
          </div>

          <p className="mt-5 font-medium text-foreground">
            {isDragActive
              ? "Drop your document here"
              : "Drag and drop a document"}
          </p>

          <p className="mt-1.5 text-sm text-text-secondary">
            or click to browse your computer
          </p>

          <span className="btn-secondary mt-6 inline-flex pointer-events-none">
            Browse Files
          </span>

          <p className="mt-5 text-xs text-text-muted">
            <span className="font-medium text-text-secondary">PDF</span> (Full Source Verification) · DOCX, PNG, JPG (Text Extraction)
          </p>
        </div>
      ) : (
        <div className="rounded-2xl border border-border bg-surface-soft/50 p-5">
          <div className="flex items-center gap-4">
            <div className="file-icon-wrap h-12 w-12 shrink-0">
              <FileText className="h-6 w-6" strokeWidth={1.75} />
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-foreground">
                {selectedFile.name}
              </p>

              <p className="mt-1 text-sm text-text-secondary">
                {formatBytes(selectedFile.size)}
              </p>
            </div>

            {!uploading && (
              <button
                type="button"
                onClick={clearFile}
                className="rounded-lg p-2 text-text-muted transition duration-200 hover:bg-surface hover:text-foreground"
                aria-label="Remove selected file"
              >
                <X className="h-5 w-5" strokeWidth={1.75} />
              </button>
            )}
          </div>

          {progress > 0 && (
            <div className="mt-5">
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="text-text-secondary">
                  {progress === 100
                    ? "Upload complete"
                    : waking
                      ? "Waking processing service..."
                      : progress < 35
                        ? "Connecting to backend..."
                        : "Uploading and validating"}
                </span>

                <span className="font-medium text-foreground">
                  {progress}%
                </span>
              </div>

              <div className="progress-violet">
                <div
                  className="progress-violet-fill"
                  style={{ width: `${progress}%` }}
                />
              </div>

              {waking && (
                <p className="mt-2 text-xs text-text-muted">
                  The backend was idle and is spinning back up. This can
                  take up to 90 seconds on the free tier — please keep
                  this tab open.
                </p>
              )}
            </div>
          )}

          <button
            type="button"
            onClick={uploadDocument}
            disabled={uploading || progress === 100}
            className="btn-primary mt-5 w-full disabled:cursor-not-allowed disabled:opacity-60"
          >
            {uploading ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : progress === 100 ? (
              <>
                <CheckCircle2 className="h-4 w-4" />
                Uploaded
              </>
            ) : (
              <>
                <UploadCloud className="h-4 w-4" />
                Upload document
              </>
            )}
          </button>
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">
          {error}
        </div>
      )}

      {pendingDuplicate && (
        <DuplicateDialog
          existingDocument={pendingDuplicate.existingDocument}
          busy={resolving}
          onUseExisting={() =>
            handleDuplicateResolution("use_existing")
          }
          onUploadAnyway={() =>
            handleDuplicateResolution("upload_anyway")
          }
          onCancel={handleCancelDuplicate}
        />
      )}

      {pendingPortfolio && (
        <PortfolioPicker
          files={pendingPortfolio.files}
          busy={selectingPortfolioFile}
          onSelect={handlePortfolioSelection}
          onCancel={handleCancelPortfolio}
        />
      )}
    </div>
  );
}
