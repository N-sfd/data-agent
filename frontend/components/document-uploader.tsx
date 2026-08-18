"use client";

import { useCallback, useState } from "react";
import { useDropzone } from "react-dropzone";
import {
  CheckCircle2,
  FileText,
  Loader2,
  UploadCloud,
  X,
} from "lucide-react";

import DuplicateDialog from "@/components/duplicate-dialog";
import { apiFetch } from "@/lib/api";
import { resolveDuplicate } from "@/lib/documents";
import { formatBytes } from "@/lib/format";
import type {
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

export default function DocumentUploader({
  onUploadComplete,
}: DocumentUploaderProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [pendingDuplicate, setPendingDuplicate] =
    useState<PendingDuplicate | null>(null);
  const [resolving, setResolving] = useState(false);

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

  async function uploadDocument() {
    if (!selectedFile) return;

    setUploading(true);
    setError("");
    setProgress(15);

    try {
      const formData = new FormData();

      formData.append("file", selectedFile);

      setProgress(35);

      const response = await apiFetch("/api/documents/upload", {
          method: "POST",
          body: formData,
        });

      setProgress(80);

      const result = await response.json();

      if (!response.ok) {
        const detail =
          typeof result.detail === "string"
            ? result.detail
            : result.detail?.message ?? "Upload failed.";

        throw new Error(detail);
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
      setProgress(0);

      setError(
        uploadError instanceof Error
          ? uploadError.message
          : "Unable to upload the PDF.",
      );
    } finally {
      setUploading(false);
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

  function clearFile() {
    setSelectedFile(null);
    setProgress(0);
    setError("");
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-5">
        <p className="text-sm font-semibold text-blue-600">
          Financial Document
        </p>

        <h2 className="mt-1 text-xl font-semibold text-slate-950">
          Upload document
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          Upload a contract, financial report, invoice, budget,
          statement, or scanned agreement for analysis.
        </p>
      </div>

      {!selectedFile ? (
        <div
          {...getRootProps()}
          className={[
            "cursor-pointer rounded-2xl border-2 border-dashed p-8",
            "text-center transition",
            isDragActive
              ? "border-blue-500 bg-blue-50"
              : "border-slate-300 hover:border-blue-400 hover:bg-slate-50",
          ].join(" ")}
        >
          <input {...getInputProps()} />

          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50">
            <UploadCloud className="h-7 w-7 text-blue-600" />
          </div>

          <p className="mt-4 font-medium text-slate-900">
            {isDragActive
              ? "Drop your document here"
              : "Drag and drop a document"}
          </p>

          <p className="mt-1 text-sm text-slate-500">
            or click to browse your computer
          </p>

          <p className="mt-4 text-xs text-slate-400">
            PDF · DOCX · PNG · JPG · Maximum size controlled by
            your backend
          </p>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-red-50">
              <FileText className="h-6 w-6 text-red-600" />
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-slate-900">
                {selectedFile.name}
              </p>

              <p className="mt-1 text-sm text-slate-500">
                {formatBytes(selectedFile.size)}
              </p>
            </div>

            {!uploading && (
              <button
                type="button"
                onClick={clearFile}
                className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-200 hover:text-slate-700"
                aria-label="Remove selected file"
              >
                <X className="h-5 w-5" />
              </button>
            )}
          </div>

          {progress > 0 && (
            <div className="mt-4">
              <div className="mb-2 flex items-center justify-between text-xs">
                <span className="text-slate-500">
                  {progress === 100
                    ? "Upload complete"
                    : "Uploading and validating"}
                </span>

                <span className="font-medium text-slate-700">
                  {progress}%
                </span>
              </div>

              <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all duration-300"
                  style={{
                    width: `${progress}%`,
                  }}
                />
              </div>
            </div>
          )}

          <button
            type="button"
            onClick={uploadDocument}
            disabled={uploading || progress === 100}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
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
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
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
    </div>
  );
}
