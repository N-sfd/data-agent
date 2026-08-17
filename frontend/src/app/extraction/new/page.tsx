"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import { SplitSquareHorizontal, Sparkles } from "lucide-react";

import AiProviderNotice from "@/components/ai-provider-notice";
import AnalysisRequest from "@/components/analysis-request";
import ClassificationCard from "@/components/classification-card";
import DocumentCard from "@/components/document-card";
import DocumentUploader from "@/components/document-uploader";
import ExtractedPages from "@/components/extracted-pages";
import ImportSourceTabs from "@/components/import-source-tabs";
import IngestionChecklist from "@/components/ingestion-checklist";
import MetadataGrid from "@/components/metadata-grid";
import ProcessingStatus from "@/components/processing-status";
import RelationshipCard from "@/components/relationship-card";
import StructuredOutputPanel from "@/components/structured-output-panel";
import UniversalResults from "@/components/universal-results";
import {
  type AiStatus,
  getAiStatus,
} from "@/lib/ai-status";
import {
  analyzeContract,
  confirmRelationship,
  extractDocumentPages,
  getDocumentPages,
  getStructuredOutput,
  universalExtract,
} from "@/lib/documents";
import { listExtractionModels } from "@/lib/extraction-models";
import type {
  ContractAnalysisResult,
  DocumentPage,
  ExtractionModel,
  ExtractionSummary,
  RelationshipAction,
  StructuredContractOutput,
  UniversalExtractionResult,
  UploadedDocument,
} from "@/types/document";

export default function NewExtractionPage() {
  const [document, setDocument] =
    useState<UploadedDocument | null>(null);

  const [extraction, setExtraction] =
    useState<ExtractionSummary | null>(null);

  const [pages, setPages] = useState<DocumentPage[]>([]);

  const [extracting, setExtracting] = useState(false);

  const [universalResult, setUniversalResult] =
    useState<UniversalExtractionResult | null>(null);

  const [workflowError, setWorkflowError] = useState("");

  const [contractAnalysis, setContractAnalysis] =
    useState<ContractAnalysisResult | null>(null);

  const [analyzingContract, setAnalyzingContract] =
    useState(false);

  const [contractAnalysisError, setContractAnalysisError] =
    useState("");

  const [relationshipBusy, setRelationshipBusy] =
    useState(false);

  const [structuredOutput, setStructuredOutput] =
    useState<StructuredContractOutput | null>(null);

  const [aiStatus, setAiStatus] = useState<AiStatus | null>(
    null,
  );

  const [extractionModels, setExtractionModels] = useState<
    ExtractionModel[]
  >([]);
  const [selectedModelId, setSelectedModelId] = useState<
    number | null
  >(null);

  useEffect(() => {
    let active = true;

    getAiStatus().then((status) => {
      if (active) {
        setAiStatus(status);
      }
    });

    listExtractionModels()
      .then((models) => {
        if (active) setExtractionModels(models);
      })
      .catch(() => {
        // Non-fatal — the analyze button still works without models.
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
    setContractAnalysis(null);
    setContractAnalysisError("");
    setStructuredOutput(null);
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

  async function handleAnalyzeContract() {
    if (!document) {
      return;
    }

    setAnalyzingContract(true);
    setContractAnalysisError("");
    setStructuredOutput(null);

    try {
      const result = await analyzeContract(
        document.document_id,
        selectedModelId,
      );

      setContractAnalysis(result);

      if (result.metadata_fields.length > 0) {
        try {
          const structured = await getStructuredOutput(
            document.document_id,
          );

          setStructuredOutput(structured);
        } catch {
          // Structured output is a secondary view of the same
          // data already shown in the metadata grid — not worth
          // surfacing a separate error banner if it fails.
        }
      }
    } catch (error) {
      setContractAnalysisError(
        error instanceof Error
          ? error.message
          : "Contract analysis failed.",
      );
    } finally {
      setAnalyzingContract(false);
    }
  }

  async function handleRelationshipAction(
    action: RelationshipAction,
  ) {
    if (!document || !contractAnalysis?.relationship) {
      return;
    }

    setRelationshipBusy(true);

    try {
      const result = await confirmRelationship(
        document.document_id,
        action,
      );

      setContractAnalysis({
        ...contractAnalysis,
        relationship: result.relationship,
      });
    } catch (error) {
      setContractAnalysisError(
        error instanceof Error
          ? error.message
          : "Unable to resolve the relationship.",
      );
    } finally {
      setRelationshipBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-8">
        <p className="text-sm font-semibold text-blue-600">
          Contract Data Extraction
        </p>
        <h1 className="mt-1 text-2xl font-semibold text-slate-950">
          Turn agreements into structured intelligence
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Upload → extract → ask anything → review
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <section className="space-y-6">
          <AiProviderNotice
            show={Boolean(aiStatus?.show_dev_warning)}
            provider={aiStatus?.provider}
            model={aiStatus?.model}
            fallbackEnabled={aiStatus?.fallback_enabled}
            mode={aiStatus?.mode}
          />

          <DocumentUploader onUploadComplete={handleUploadComplete} />

          <ImportSourceTabs />

          {document && (
            <DocumentCard document={document} />
          )}

          {document && (
            <IngestionChecklist
              steps={document.pipeline_log ?? []}
            />
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

          {document && extraction && (
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <p className="text-sm font-semibold text-slate-950">
                Contract Intelligence
              </p>
              <p className="mt-1 text-sm text-slate-500">
                Classify this document, extract its structured
                metadata, and detect any parent contract.
              </p>

              {extractionModels.length > 0 && (
                <label className="mt-4 block text-xs text-slate-500">
                  Extraction Model (optional)
                  <select
                    value={selectedModelId ?? ""}
                    onChange={(event) =>
                      setSelectedModelId(
                        event.target.value
                          ? Number(event.target.value)
                          : null,
                      )
                    }
                    className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800"
                  >
                    <option value="">None</option>
                    {extractionModels.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}

              <button
                type="button"
                onClick={handleAnalyzeContract}
                disabled={analyzingContract}
                className="mt-4 inline-flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Sparkles className="h-4 w-4" />
                {analyzingContract
                  ? "Analyzing..."
                  : "Analyze Contract"}
              </button>

              {contractAnalysisError && (
                <div className="mt-3 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                  {contractAnalysisError}
                </div>
              )}

              {contractAnalysis && (
                <Link
                  href={`/documents/${document.document_id}/review`}
                  className="mt-3 inline-flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 px-4 py-2.5 text-sm font-semibold text-blue-700 transition hover:bg-blue-100"
                >
                  <SplitSquareHorizontal className="h-4 w-4" />
                  Open Review Workspace
                </Link>
              )}
            </div>
          )}

          {workflowError && (
            <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
              {workflowError}
            </div>
          )}
        </section>

        <section className="space-y-6">
          {contractAnalysis && (
            <ClassificationCard
              classification={contractAnalysis.classification}
            />
          )}

          {contractAnalysis?.relationship && (
            <RelationshipCard
              relationship={contractAnalysis.relationship}
              busy={relationshipBusy}
              onConfirm={() =>
                handleRelationshipAction("confirm")
              }
              onReject={() =>
                handleRelationshipAction("reject")
              }
            />
          )}

          {contractAnalysis && (
            <MetadataGrid
              fields={contractAnalysis.metadata_fields}
            />
          )}

          {structuredOutput && (
            <StructuredOutputPanel data={structuredOutput} />
          )}

          {universalResult && (
            <UniversalResults result={universalResult} />
          )}

          {document && (
            <ExtractedPages pages={pages} />
          )}
        </section>
      </div>
    </div>
  );
}
