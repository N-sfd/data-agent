"use client";

import { useEffect, useState } from "react";

import AiProviderNotice from "@/components/ai-provider-notice";
import AnalysisRequest from "@/components/analysis-request";
import DocumentCard from "@/components/document-card";
import ExtractedPages from "@/components/extracted-pages";
import PdfUploader from "@/components/pdf-uploader";
import ProcessingStatus from "@/components/processing-status";
import UniversalResults from "@/components/universal-results";
import {
  type AiStatus,
  getAiStatus,
} from "@/lib/ai-status";
import {
  extractDocumentPages,
  getDocumentPages,
  universalExtract,
} from "@/lib/documents";
import type {
  DocumentPage,
  ExtractionSummary,
  UniversalExtractionResult,
  UploadedDocument,
} from "@/types/document";

export default function Home() {
  const [document, setDocument] =
    useState<UploadedDocument | null>(null);

  const [extraction, setExtraction] =
    useState<ExtractionSummary | null>(null);

  const [pages, setPages] = useState<DocumentPage[]>([]);

  const [extracting, setExtracting] = useState(false);

  const [universalResult, setUniversalResult] =
    useState<UniversalExtractionResult | null>(null);

  const [workflowError, setWorkflowError] = useState("");

  const [aiStatus, setAiStatus] = useState<AiStatus | null>(
    null,
  );

  useEffect(() => {
    let active = true;

    getAiStatus().then((status) => {
      if (active) {
        setAiStatus(status);
      }
    });

    return () => {
      active = false;
    };
  }, []);

  async function handleUploadComplete(
    uploadedDocument: UploadedDocument,
  ) {
    setDocument(uploadedDocument);
    setExtraction(null);
    setPages([]);
    setUniversalResult(null);
    setWorkflowError("");
    setExtracting(true);

    try {
      const extractionResult = await extractDocumentPages(
        uploadedDocument.document_id,
      );

      setExtraction(extractionResult);

      const extractedPages = await getDocumentPages(
        uploadedDocument.document_id,
      );

      setPages(extractedPages);
    } catch (error) {
      setWorkflowError(
        error instanceof Error
          ? error.message
          : "Page extraction failed.",
      );
    } finally {
      setExtracting(false);
    }
  }

  async function handleAnalyze(instruction: string) {
    if (!document) {
      return;
    }

    const result = await universalExtract(
      document.document_id,
      instruction,
    );

    setUniversalResult(result);
  }

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
          <div>
            <p className="text-sm font-semibold text-blue-600">
              Data Agent
            </p>
            <h1 className="mt-1 text-xl font-semibold text-slate-950">
              Universal document extraction
            </h1>
          </div>

          <p className="hidden text-sm text-slate-500 sm:block">
            Upload → extract → ask anything → review
          </p>
        </div>
      </header>

      <main className="mx-auto grid max-w-6xl gap-6 px-6 py-8 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <section className="space-y-6">
          <AiProviderNotice
            show={Boolean(aiStatus?.show_dev_warning)}
            provider={aiStatus?.provider}
            model={aiStatus?.model}
          />

          <PdfUploader onUploadComplete={handleUploadComplete} />

          {document && (
            <DocumentCard document={document} />
          )}

          {document && (
            <ProcessingStatus
              document={document}
              extraction={extraction}
              extracting={extracting}
            />
          )}

          {document && (
            <AnalysisRequest
              disabled={!extraction || extracting}
              onAnalyze={handleAnalyze}
            />
          )}

          {workflowError && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {workflowError}
            </div>
          )}
        </section>

        <section className="space-y-6">
          {universalResult && (
            <UniversalResults result={universalResult} />
          )}

          {document && (
            <ExtractedPages pages={pages} />
          )}
        </section>
      </main>
    </div>
  );
}
