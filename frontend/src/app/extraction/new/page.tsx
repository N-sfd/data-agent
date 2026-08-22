"use client";

import { useEffect, useRef, useState } from "react";


import { Sparkles } from "lucide-react";

import ContentSection from "@/components/layout/ContentSection";
import PageHero from "@/components/layout/PageHero";
import ExtractionStatusPanel from "@/components/extraction-status-panel";
import WorkflowBreadcrumb from "@/components/workflow-breadcrumb";
import ExtractionResultsWorkspace from "@/components/extraction/extraction-results-workspace";
import AnalysisRequest from "@/components/analysis-request";
import DocumentCard from "@/components/document-card";
import DocumentUploader from "@/components/document-uploader";
import ImportSourceTabs from "@/components/import-source-tabs";
import IngestionChecklist from "@/components/ingestion-checklist";
import ProcessingStatus from "@/components/processing-status";
import {
  analyzeContract,
  confirmRelationship,
  extractDocumentPages,
  getDocumentPages,
  getExtractionProgress,
  getStructuredOutput,
  universalExtract,
} from "@/lib/documents";
import { listExtractionModels } from "@/lib/extraction-models";
import type {
  ContractAnalysisResult,
  DocumentPage,
  ExtractionModel,
  ExtractionProgress,
  ExtractionSummary,
  RelationshipAction,
  StructuredContractOutput,
  UniversalExtractionResult,
  UploadedDocument,
} from "@/types/document";

const ANALYZE_STAGE_MESSAGES = [
  "Classifying document... Identifying document type, contract side, language, and status.",
  "Detecting related agreements... Checking parent and child contract relationships.",
];

export default function NewExtractionPage() {
  const [document, setDocument] =
    useState<UploadedDocument | null>(null);

  const [extraction, setExtraction] =
    useState<ExtractionSummary | null>(null);

  const [pages, setPages] = useState<DocumentPage[]>([]);

  const [extracting, setExtracting] = useState(false);

  const [progress, setProgress] =
    useState<ExtractionProgress | null>(null);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [waking, setWaking] = useState(false);

  const [analyzeStageIndex, setAnalyzeStageIndex] = useState(0);
  const [wasAnalyzing, setWasAnalyzing] = useState(false);

  const resultsWorkspaceRef = useRef<HTMLDivElement | null>(null);

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

  useEffect(() => {
    if (!extracting || !document) {
      return;
    }

    let active = true;
    const documentId = document.document_id;
    const startedAt = Date.now();

    async function poll() {
      try {
        const result = await getExtractionProgress(documentId);

        if (active) {
          setProgress(result);
        }
      } catch {
        // Progress polling is best-effort — keep showing the last
        // known state rather than surfacing an error for it.
      }
    }

    poll();
    const progressInterval = setInterval(poll, 1500);

    const elapsedInterval = setInterval(() => {
      setElapsedSeconds(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);

    return () => {
      active = false;
      clearInterval(progressInterval);
      clearInterval(elapsedInterval);
    };
  }, [extracting, document]);

  if (analyzingContract !== wasAnalyzing) {
    setWasAnalyzing(analyzingContract);

    if (!analyzingContract) {
      setAnalyzeStageIndex(0);
    }
  }

  useEffect(() => {
    if (!analyzingContract) {
      return;
    }

    const interval = setInterval(() => {
      setAnalyzeStageIndex(
        (index) => (index + 1) % ANALYZE_STAGE_MESSAGES.length,
      );
    }, 3000);

    return () => clearInterval(interval);
  }, [analyzingContract]);

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
    setProgress(null);
    setElapsedSeconds(0);
    setWaking(false);
    setExtracting(true);

    try {
      const extractionResult = await extractDocumentPages(
        uploadedDocument.document_id,
        () => setWaking(true),
      );

      setWaking(false);
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
      setWaking(false);
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
                progress={progress}
                elapsedSeconds={elapsedSeconds}
                waking={waking}
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

          {document && extraction && !contractAnalysis && (
            <div className="editorial-card animate-fade-in p-8">
              <p className="text-base font-medium text-foreground">
                Contract Intelligence
              </p>
              <p className="mt-2 text-sm leading-6 text-text-secondary">
                Classify this document, extract its structured metadata, and
                detect any parent contract.
              </p>

              {analyzingContract && (
                <div className="mt-4 rounded-xl bg-surface-soft px-3.5 py-2.5 text-xs text-text-secondary">
                  {ANALYZE_STAGE_MESSAGES[analyzeStageIndex]}
                </div>
              )}

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
                {analyzingContract ? (
                  <span className="h-2 w-2 animate-pulse rounded-full bg-white" />
                ) : (
                  <Sparkles className="h-4 w-4" />
                )}
                {analyzingContract ? "Analyzing..." : "Run Extraction"}
              </button>

              {contractAnalysisError && (
                <div className="mt-4 rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">
                  {contractAnalysisError}
                </div>
              )}
            </div>
          )}

          {document && contractAnalysis && extraction && (
            <div className="editorial-card animate-fade-in p-8">
              <p className="text-base font-medium text-foreground">
                Ready for review
              </p>

              <ul className="mt-3 space-y-1 text-sm text-text-secondary">
                <li>{extraction.pages_processed} pages processed</li>
                <li>Document classified</li>
                <li>Relationships analyzed</li>
                <li>
                  {contractAnalysis.metadata_fields.length} metadata fields
                  extracted
                </li>
              </ul>

              <button
                type="button"
                onClick={() =>
                  resultsWorkspaceRef.current?.scrollIntoView({
                    behavior: "smooth",
                  })
                }
                className="btn-primary mt-5"
              >
                Review Extraction
              </button>
            </div>
          )}

          {workflowError && (
            <div className="rounded-xl border border-danger/20 bg-danger/5 p-4">
              <p className="text-sm font-medium text-danger">
                Extraction could not be completed
              </p>
              <p className="mt-1 text-sm leading-6 text-danger/80">
                The document was uploaded successfully, but page extraction
                failed.
              </p>

              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => document && handleUploadComplete(document)}
                  className="btn-secondary text-sm"
                >
                  Retry Extraction
                </button>

                <details className="text-xs text-danger/80">
                  <summary className="cursor-pointer select-none">
                    View Details
                  </summary>
                  <p className="mt-1">{workflowError}</p>
                </details>
              </div>
            </div>
          )}
        </section>
      </div>

      {contractAnalysis && document && (
        <div ref={resultsWorkspaceRef}>
          <ExtractionResultsWorkspace
            document={document}
            analysis={contractAnalysis}
            pages={pages}
            structuredOutput={structuredOutput}
            universalResult={universalResult}
            extractingPages={extracting}
            pagesError={workflowError}
            onRetryPages={() => handleUploadComplete(document)}
            relationshipBusy={relationshipBusy}
            onRelationshipAction={handleRelationshipAction}
            onRelationshipChange={(relationship) =>
              setContractAnalysis((current) =>
                current ? { ...current, relationship } : current,
              )
            }
          />
        </div>
      )}
      </ContentSection>
    </>
  );
}
