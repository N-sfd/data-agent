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

import { apiUrl } from "@/lib/api";
import { formatBytes } from "@/lib/format";
import type { UploadedDocument } from "@/types/document";

interface PdfUploaderProps {
  onUploadComplete: (document: UploadedDocument) => void;
}

export default function PdfUploader({
  onUploadComplete,
}: PdfUploaderProps) {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");

  const onDrop = useCallback((acceptedFiles: File[]) => {
    setError("");

    const file = acceptedFiles[0];

    if (!file) return;

    if (
      file.type !== "application/pdf" &&
      !file.name.toLowerCase().endsWith(".pdf")
    ) {
      setError("Please select a PDF document.");
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
    },
    multiple: false,
    maxFiles: 1,
  });

  async function uploadPdf() {
    if (!selectedFile) return;

    setUploading(true);
    setError("");
    setProgress(15);

    try {
      const formData = new FormData();

      formData.append("file", selectedFile);

      setProgress(35);

      const response = await fetch(
        apiUrl("/api/documents/upload"),
        {
          method: "POST",
          body: formData,
        },
      );

      setProgress(80);

      const result = await response.json();

      if (!response.ok) {
        const detail =
          typeof result.detail === "string"
            ? result.detail
            : result.detail?.message ?? "Upload failed.";

        throw new Error(detail);
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
          Upload PDF
        </h2>

        <p className="mt-2 text-sm leading-6 text-slate-500">
          Upload a financial report, invoice document, budget,
          statement, or other PDF for analysis.
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
              ? "Drop your PDF here"
              : "Drag and drop a PDF"}
          </p>

          <p className="mt-1 text-sm text-slate-500">
            or click to browse your computer
          </p>

          <p className="mt-4 text-xs text-slate-400">
            PDF only · Maximum size controlled by your backend
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
            onClick={uploadPdf}
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
                Upload PDF
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
    </div>
  );
}