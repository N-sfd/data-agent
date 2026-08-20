"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import { SplitSquareHorizontal, Sparkles } from "lucide-react";

import ContentSection from "@/components/layout/ContentSection";
import PageHero from "@/components/layout/PageHero";
import ExtractionStatusPanel from "@/components/extraction-status-panel";
import WorkflowBreadcrumb from "@/components/workflow-breadcrumb";
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

  const [extractionModels, setExtractionModels] = useState<
    ExtractionModel[]
  >([]);
  const [selectedModelId, setSelectedModelId] = useState<
    number | null
  >(null);

  useEffect(() => {
    let active = true;

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
        "Consult America",
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
    <>
      <PageHero
        eyebrow="Store / Extraction Agent"
        title={
          <>
            Turn agreements into
            <br />
            structured intelligence
          </>
        }
        description="Convert contracts and financial documents into structured, searchable intelligence with source-level traceability."
      />

      <ContentSection>
        <div className="mb-8">
          <WorkflowBreadcrumb
            activeStep={
              contractAnalysis
                ? "review"
                : extraction
                  ? "extract"
                  : document
                    ? "upload"
                    : "upload"
            }
          />
        </div>

        <div className="grid gap-8 lg:grid-cols-2">
          <section className="space-y-8">
            <DocumentUploader onUploadComplete={handleUploadComplete} />

            <ImportSourceTabs />

            {document && <DocumentCard document={document} />}
          </section>

          <section className="space-y-8">
            <div className="editorial-card p-8">
              <ExtractionStatusPanel
                document={document}
                extraction={extraction}
                extracting={extracting}
                contractAnalyzed={Boolean(contractAnalysis)}
              />

              {document && (
                <>
                  <IngestionChecklist steps={document.pipeline_log ?? []} />
                  <ProcessingStatus
                    document={document}
                    extraction={extraction}
                    extracting={extracting}
                  />
                </>
              )}
            </div>

          {document && (
            <AnalysisRequest
              disabled={!extraction || extracting}
              onAnalyze={handleAnalyze}
            />
          )}

          {document && extraction && (
            <div className="editorial-card p-8">
              <p className="text-base font-medium text-foreground">
                Contract Intelligence
              </p>
              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Classify this document, extract its structured metadata, and
                detect any parent contract.
              </p>

              {extractionModels.length > 0 && (
                <label className="mt-5 block text-xs text-text-secondary">
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
                    className="mt-1.5 w-full rounded-xl border border-border bg-surface px-3 py-2.5 text-sm text-foreground outline-none focus:border-primary/30"
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
                className="btn-primary mt-5 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Sparkles className="h-4 w-4" />
                {analyzingContract ? "Analyzing..." : "Run Extraction"}
              </button>

              {contractAnalysisError && (
                <div className="mt-4 rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">
                  {contractAnalysisError}
                </div>
              )}

              {contractAnalysis && (
                <Link
                  href={`/documents/${document.document_id}/review`}
                  className="btn-secondary mt-4"
                >
                  <SplitSquareHorizontal className="h-4 w-4" />
                  Open Review Workspace
                </Link>
              )}
            </div>
          )}

          {workflowError && (
            <div className="rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">
              {workflowError}
            </div>
          )}
        </section>

        <section className="space-y-6 lg:col-span-2">
          {contractAnalysis && (
            <ClassificationCard
              classification={contractAnalysis.classification}
            />
          )}

          {contractAnalysis && document && (
            <RelationshipCard
              documentId={document.document_id}
              relationship={contractAnalysis.relationship}
              reviewerName="Consult America"
              busy={relationshipBusy}
              onConfirm={() =>
                handleRelationshipAction("confirm")
              }
              onReject={() =>
                handleRelationshipAction("reject")
              }
              onRelationshipChange={(relationship) =>
                setContractAnalysis((current) =>
                  current ? { ...current, relationship } : current,
                )
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
            <ExtractedPages
              pages={pages}
              extracting={extracting}
              error={workflowError}
              onRetry={() =>
                handleUploadComplete(document)
              }
            />
          )}
        </section>
      </div>
      </ContentSection>
    </>
  );
}
