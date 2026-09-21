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
import { wakeBackend } from "@/lib/api";
import { resolveDuplicate, selectPortfolioFile } from "@/lib/documents";
import { uploadFileWithProgress } from "@/lib/upload";
import { formatBytes } from "@/lib/format";
import type {
  EmbeddedFileSummary,
  ExistingDocumentSummary,
  UploadedDocument,
} from "@/types/document";

const ACCEPTED_EXTENSIONS = [
  ".pdf",
  ".docx",
  ".doc",
  ".xlsx",
  ".xls",
  ".pptx",
  ".ppt",
  ".txt",
  ".csv",
  ".rtf",
  ".html",
  ".htm",
  ".png",
  ".jpg",
  ".jpeg",
  ".tif",
  ".tiff",
  ".bmp",
  ".webp",
];

/**
 * Explicit upload lifecycle. "queued"/"processing"/"complete" are not
 * represented here — this component unmounts the instant onUploadComplete
 * fires, handing off to extraction/new/page.tsx's already-real (non-fake)
 * processing progress (extraction-live-progress.tsx).
 */
type UploadStage =
  | "idle"
  | "file_selected"
  | "service_starting"
  | "uploading"
  | "upload_complete"
  | "failed";

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
  const [stage, setStage] = useState<UploadStage>("idle");
  const [uploadFraction, setUploadFraction] = useState(0);
  const [error, setError] = useState("");
  const [pendingDuplicate, setPendingDuplicate] =
    useState<PendingDuplicate | null>(null);
  const [resolving, setResolving] = useState(false);
  const [pendingPortfolio, setPendingPortfolio] =
    useState<PendingPortfolio | null>(null);
  const [selectingPortfolioFile, setSelectingPortfolioFile] =
    useState(false);

  // Pre-warm: fire once when this page mounts, independent of file
  // selection, so the backend may already be awake by the time the user
  // picks a document. serviceReadyRef (not state) avoids a stale-closure
  // read inside ensureServiceReady after an `await`.
  const serviceReadyRef = useRef(false);
  const prewarmRef = useRef<Promise<void> | null>(null);

  useEffect(() => {
    prewarmRef.current = wakeBackend()
      .then(() => {
        serviceReadyRef.current = true;
      })
      .catch(() => {
        // Swallow here — the user may never upload this session. An
        // actual upload attempt below gets its own fresh wake sequence.
      });
  }, []);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setError("");

    const file = acceptedFiles[0];

    if (!file) return;

    const extension = file.name
      .toLowerCase()
      .slice(file.name.lastIndexOf("."));

    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      setError(
        "Please select a supported business document (PDF, Office, text, or image).",
      );
      return;
    }

    setSelectedFile(file);
    setStage("file_selected");
    setUploadFraction(0);
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
      "application/msword": [".doc"],
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        [".xlsx"],
      "application/vnd.ms-excel": [".xls"],
      "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        [".pptx"],
      "application/vnd.ms-powerpoint": [".ppt"],
      "text/plain": [".txt"],
      "text/csv": [".csv"],
      "application/rtf": [".rtf"],
      "text/rtf": [".rtf"],
      "text/html": [".html", ".htm"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
      "image/tiff": [".tif", ".tiff"],
      "image/bmp": [".bmp"],
      "image/webp": [".webp"],
    },
    multiple: false,
    maxFiles: 1,
  });

  async function ensureServiceReady() {
    if (serviceReadyRef.current) return;

    setStage("service_starting");

    if (prewarmRef.current) {
      await prewarmRef.current;
    }

    if (serviceReadyRef.current) return;

    // Pre-warm hadn't started, was still running, or failed — the user
    // has now explicitly asked to upload, so make one more attempt.
    await wakeBackend();
    serviceReadyRef.current = true;
  }

  async function uploadDocument() {
    if (!selectedFile) return;

    setError("");

    try {
      await ensureServiceReady();

      setStage("uploading");
      setUploadFraction(0);

      const result = await uploadFileWithProgress<UploadedDocument>(
        "/api/documents/upload",
        selectedFile,
        setUploadFraction,
      );

      if (result.status === "portfolio_pending" && result.embedded_files) {
        setPendingPortfolio({
          documentId: result.document_id,
          files: result.embedded_files,
        });
        setStage("file_selected");
        return;
      }

      if (result.duplicate && result.existing_document) {
        setPendingDuplicate({
          documentId: result.document_id,
          originalFilename: result.original_filename,
          existingDocument: result.existing_document,
        });
        setStage("file_selected");
        return;
      }

      setStage("upload_complete");
      onUploadComplete(result);
    } catch (uploadError) {
      setStage("failed");
      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to upload the document.",
      );
    }
  }

  async function handleDuplicateResolution(
    action: "use_existing" | "upload_anyway",
  ) {
    if (!pendingDuplicate) return;

    setResolving(true);
    setError("");

    try {
      const existingId = String(
        pendingDuplicate.existingDocument.document_id,
      );

      try {
        const result = await resolveDuplicate(
          pendingDuplicate.documentId,
          action,
          pendingDuplicate.originalFilename,
          () => setResolving(true),
          existingId,
        );

        setPendingDuplicate(null);
        setStage("upload_complete");
        onUploadComplete(result);
        return;
      } catch (resolveError) {
        const message =
          resolveError instanceof Error
            ? resolveError.message
            : "Unable to resolve the duplicate upload.";

        // Staged temp file expired (common on multi-instance hosts).
        // Re-upload the selected file with allow_duplicate=true.
        if (
          action === "upload_anyway" &&
          selectedFile &&
          (message.includes("STAGED_UPLOAD_EXPIRED") ||
            message.includes("No pending upload found"))
        ) {
          const result = await uploadFileWithProgress<UploadedDocument>(
            "/api/documents/upload?allow_duplicate=true",
            selectedFile,
            setUploadFraction,
          );
          setPendingDuplicate(null);
          setStage("upload_complete");
          onUploadComplete(result);
          return;
        }

        // use_existing with missing stage still works when existing id is sent;
        // if that fails, surface the error.
        throw resolveError instanceof Error
          ? resolveError
          : new Error(message);
      }
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
    setStage("file_selected");
  }

  async function handlePortfolioSelection(filename: string) {
    if (!pendingPortfolio) return;

    setSelectingPortfolioFile(true);
    setError("");

    try {
      const result = await selectPortfolioFile(
        pendingPortfolio.documentId,
        filename,
        () => setSelectingPortfolioFile(true),
      );

      setPendingPortfolio(null);

      if (result.duplicate && result.existing_document) {
        setPendingDuplicate({
          documentId: result.document_id,
          originalFilename: result.original_filename,
          existingDocument: result.existing_document,
        });
        setStage("file_selected");
        return;
      }

      setStage("upload_complete");
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
    setStage("file_selected");
  }

  function clearFile() {
    setSelectedFile(null);
    setStage("idle");
    setUploadFraction(0);
    setError("");
  }

  const busy = stage === "service_starting" || stage === "uploading";
  const percent = Math.round(uploadFraction * 100);

  return (
    <div className="editorial-card p-8">
      <div className="mb-6">
        <h2 className="text-xl font-medium tracking-tight text-foreground">
          Upload document
        </h2>

        <p className="mt-2 text-sm leading-6 text-text-secondary">
          Contracts, financial documents, lab records, BRDs, and scanned files.
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
            <span className="font-medium text-text-secondary">PDF</span>{" "}
            (full source) · Office / text (native extract) · Images (OCR)
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

            {!busy && stage !== "upload_complete" && (
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

          {stage === "service_starting" && (
            <div className="mt-5">
              <p className="text-sm font-medium text-foreground">
                Preparing processing service…
              </p>
              <p className="mt-1 text-xs text-text-muted">
                The document is ready and will upload automatically once
                the service is available — this can take up to 90 seconds
                on the free tier.
              </p>
              <div className="progress-violet mt-3">
                <div className="progress-violet-fill w-1/3 animate-[indeterminate_1.4s_ease-in-out_infinite]" />
              </div>
            </div>
          )}

          {stage === "uploading" && (
            <div className="mt-5">
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="text-text-secondary">
                  Uploading document…
                </span>
                <span className="font-medium text-foreground">
                  {percent}%
                </span>
              </div>
              <div className="progress-violet">
                <div
                  className="progress-violet-fill"
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>
          )}

          {stage === "upload_complete" && (
            <div className="mt-5">
              <div className="flex items-center gap-2 text-sm font-medium text-success">
                <CheckCircle2 className="h-4 w-4" />
                Document uploaded
              </div>
              <p className="mt-1 text-xs text-text-secondary">
                Processing started
              </p>
            </div>
          )}

          <button
            type="button"
            onClick={uploadDocument}
            disabled={busy || stage === "upload_complete"}
            className="btn-primary mt-5 w-full disabled:cursor-not-allowed disabled:opacity-60"
          >
            {stage === "service_starting" ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Starting service…
              </>
            ) : stage === "uploading" ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Uploading…
              </>
            ) : stage === "upload_complete" ? (
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
