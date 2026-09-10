"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";


import { Sparkles } from "lucide-react";

import ContentSection from "@/components/layout/ContentSection";
import PageHero from "@/components/layout/PageHero";
import WorkflowBreadcrumb from "@/components/workflow-breadcrumb";
import ExtractionResultsWorkspace from "@/components/extraction/extraction-results-workspace";
import ProcessingDetailsDrawer from "@/components/extraction/processing-details-drawer";
import TargetResults from "@/components/extraction/target-results";
import ExtractionSummaryBar from "@/components/extraction/extraction-summary-bar";
import AnalysisRequest from "@/components/analysis-request";
import UniversalResults from "@/components/universal-results";
import SourceVerificationPanel, {
  type SourceViewRequest,
} from "@/components/source-verification-panel";
import DocumentOverview from "@/components/document-overview";
import DocumentUploader from "@/components/document-uploader";
import BackendStatusBanner from "@/components/backend-status-banner";
import ImportSourceTabs from "@/components/import-source-tabs";
import {
  analyzeContract,
  confirmRelationship,
  createCustomTarget,
  deleteCustomTarget,
  detectStructures,
  discoverSchema,
  extractDocumentPages,
  extractTargetsViaJob,
  getDocument,
  getDocumentPages,
  getExtractResults,
  getExtractionProgress,
  getStructuredOutput,
  getTargets,
  renameCustomTarget,
  universalExtract,
} from "@/lib/documents";
import { listExtractionModels } from "@/lib/extraction-models";
import type {
  ContractAnalysisResult,
  DiscoverSchemaResult,
  DocumentPage,
  ExtractTargetsResult,
  ExtractionJob,
  ExtractionModel,
  ExtractionProgress,
  ExtractionSummary,
  RelationshipAction,
  StructureDetectionResult,
  StructuredContractOutput,
  UniversalExtractionResult,
  UploadedDocument,
} from "@/types/document";

function confidenceQualifier(confidence: number): string {
  if (confidence >= 0.85) return "High confidence";
  if (confidence >= 0.6) return "Medium confidence";
  return "Low confidence";
}

const ANALYZE_STAGE_MESSAGES = [
  "Classifying document... Identifying document type, contract side, language, and status.",
  "Detecting related documents... Checking parent and child relationships.",
];

export default function NewExtractionPage() {
  return (
    <Suspense fallback={null}>
      <NewExtractionPageContent />
    </Suspense>
  );
}

function NewExtractionPageContent() {
  const searchParams = useSearchParams();
  const reopenDocumentId = searchParams.get("documentId");

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
  const [targetExtractionJob, setTargetExtractionJob] =
    useState<ExtractionJob | null>(null);

  const [analyzeStageIndex, setAnalyzeStageIndex] = useState(0);
  const [wasAnalyzing, setWasAnalyzing] = useState(false);

  const resultsWorkspaceRef = useRef<HTMLDivElement | null>(null);
  const universalResultRef = useRef<HTMLDivElement | null>(null);
  const targetResultRef = useRef<HTMLDivElement | null>(null);

  const [processingDrawerOpen, setProcessingDrawerOpen] = useState(false);
  const [sourceRequest, setSourceRequest] =
    useState<SourceViewRequest | null>(null);
  // True mobile only (below sm) — tablet and up always show the source
  // pane stacked/split, no drawer needed there.
  const [mobileSourceOpen, setMobileSourceOpen] = useState(false);

  function handleViewSource(request: SourceViewRequest) {
    setSourceRequest(request);
    setMobileSourceOpen(true);
  }

  const [universalResult, setUniversalResult] =
    useState<UniversalExtractionResult | null>(null);

  const [schemaDiscovery, setSchemaDiscovery] =
    useState<DiscoverSchemaResult | null>(null);
  const [schemaDiscovering, setSchemaDiscovering] = useState(false);
  const [schemaDiscoveryError, setSchemaDiscoveryError] = useState("");

  const [targetResult, setTargetResult] =
    useState<ExtractTargetsResult | null>(null);
  const [targetResultDurationMs, setTargetResultDurationMs] = useState<
    number | null
  >(null);

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

  const [structureDetection, setStructureDetection] =
    useState<StructureDetectionResult | null>(null);

  const [extractionModels, setExtractionModels] = useState<
    ExtractionModel[]
  >([]);
  const [selectedModelId, setSelectedModelId] = useState<
    number | null
  >(null);

  useEffect(() => {
    const documentFamily = schemaDiscovery?.document_family;
    if (!documentFamily) return;

    let active = true;

    listExtractionModels(documentFamily)
      .then((models) => {
        if (active) setExtractionModels(models);
      })
      .catch(() => {
        // Non-fatal — the analyze button still works without models.
      });

    return () => {
      active = false;
    };
  }, [schemaDiscovery?.document_family]);

  // Reopen durable intelligence record — never re-extract automatically.
  useEffect(() => {
    if (!reopenDocumentId || document) return;

    let active = true;

    async function hydrate() {
      try {
        const [doc, pagesResult, targets, extractResults] =
          await Promise.all([
            getDocument(reopenDocumentId!),
            getDocumentPages(reopenDocumentId!),
            getTargets(reopenDocumentId!).catch(() => null),
            getExtractResults(reopenDocumentId!).catch(() => null),
          ]);
        if (!active) return;

        setDocument(doc);
        setPages(pagesResult);
        setExtraction({
          document_id: doc.document_id,
          status: "completed",
          total_document_pages: doc.page_count,
          pages_requested: doc.page_count,
          pages_processed: pagesResult.length || doc.page_count,
          native_pages: pagesResult.length || doc.page_count,
          ocr_required_pages: 0,
          ocr_completed_pages: 0,
          failed_pages: 0,
          page_numbers_processed: pagesResult.map((p) => p.page_number),
          warnings: [],
          completed_at: doc.uploaded_at,
        });
        if (targets) setSchemaDiscovery(targets);
        if (extractResults) {
          setTargetResult(extractResults);
          const first = extractResults.scalars[0];
          if (first?.evidence) {
            setSourceRequest({
              id: first.normalized_key,
              pageNumber: first.page,
              highlightText: first.evidence.source_text || String(first.value),
              label: first.target,
              value: String(first.value ?? ""),
              confidence: first.confidence,
              verified: first.verified,
            });
          }
        }
      } catch (error) {
        if (active) {
          setWorkflowError(
            error instanceof Error
              ? error.message
              : "Unable to reopen persisted document.",
          );
        }
      }
    }

    hydrate();
    return () => {
      active = false;
    };
  }, [reopenDocumentId, document]);

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

  async function runSchemaDiscovery(documentId: string) {
    setSchemaDiscovering(true);
    setSchemaDiscoveryError("");

    try {
      const discovery = await discoverSchema(
        documentId,
        () => setWaking(true),
      );

      setSchemaDiscovery(discovery);
    } catch (error) {
      setSchemaDiscoveryError(
        error instanceof Error
          ? error.message
          : "Schema discovery failed.",
      );
    } finally {
      setSchemaDiscovering(false);
      setWaking(false);
    }
  }

  async function handleAddCustomField(label: string) {
    if (!document) return;

    const target = await createCustomTarget(document.document_id, label);

    setSchemaDiscovery((current) =>
      current
        ? { ...current, targets: [...current.targets, target] }
        : current,
    );

    return target;
  }

  async function handleRenameCustomField(targetKey: string, label: string) {
    if (!document) return;

    const updated = await renameCustomTarget(
      document.document_id,
      targetKey,
      label,
    );

    setSchemaDiscovery((current) =>
      current
        ? {
            ...current,
            targets: current.targets.map((target) =>
              target.key === targetKey ? updated : target,
            ),
          }
        : current,
    );
  }

  async function handleDeleteCustomField(targetKey: string) {
    if (!document) return;

    await deleteCustomTarget(document.document_id, targetKey);

    setSchemaDiscovery((current) =>
      current
        ? {
            ...current,
            targets: current.targets.filter(
              (target) => target.key !== targetKey,
            ),
          }
        : current,
    );
  }

  async function handleUploadComplete(
    uploadedDocument: UploadedDocument,
  ) {
    setDocument(uploadedDocument);
    setExtraction(null);
    setPages([]);
    setUniversalResult(null);
    setTargetResult(null);
    setWorkflowError("");
    setContractAnalysis(null);
    setContractAnalysisError("");
    setStructuredOutput(null);
    setStructureDetection(null);
    setSchemaDiscovery(null);
    setSchemaDiscovering(false);
    setSchemaDiscoveryError("");
    setProgress(null);
    setElapsedSeconds(0);
    setWaking(false);
    setSourceRequest(null);
    setMobileSourceOpen(false);
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

      try {
        const detection = await detectStructures(
          uploadedDocument.document_id,
        );

        setStructureDetection(detection);
      } catch {
        // Structure detection is a convenience layer on top of a
        // successful extraction — if it fails, the overview card
        // just skips the detected-content summary.
      }

      await runSchemaDiscovery(uploadedDocument.document_id);
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

  async function handleAnalyze(
    instruction: string,
  ): Promise<UniversalExtractionResult> {
    if (!document) {
      throw new Error("Upload a document first.");
    }

    try {
      const result = await universalExtract(
        document.document_id,
        instruction,
        () => setWaking(true),
      );

      setUniversalResult(result);
      requestAnimationFrame(() => {
        universalResultRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });

      return result;
    } finally {
      setWaking(false);
    }
  }

  async function handleExtractTargets(
    targetIds: string[],
  ): Promise<ExtractTargetsResult> {
    if (!document) {
      throw new Error("Upload a document first.");
    }

    const startedAt = Date.now();

    try {
      const result = await extractTargetsViaJob(
        document.document_id,
        targetIds,
        (job) => setTargetExtractionJob(job),
        () => setWaking(true),
      );

      setTargetResult(result);
      setTargetResultDurationMs(Date.now() - startedAt);

      const first = result.scalars[0];
      if (first) {
        setSourceRequest({
          id: first.normalized_key,
          label: first.target,
          value: String(first.value ?? ""),
          pageNumber: first.page,
          highlightText: String(first.value ?? ""),
          confidence: first.confidence,
          verified: first.verified,
        });
      }

      requestAnimationFrame(() => {
        targetResultRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      });

      return result;
    } finally {
      setWaking(false);
      setTargetExtractionJob(null);
    }
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
        () => setWaking(true),
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
      setWaking(false);
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
        eyebrow="Store / Extraction"
        title={
          <>
            Source evidence first
            <br />
            across every document
          </>
        }
        description="Extract fields, tables, and clauses from contracts, financial reports, lab records, and more — then verify every value against the source PDF."
      />

      <ContentSection>
        <BackendStatusBanner />
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

        <div className="extraction-workspace -mx-[max(1.5rem,3vw)]">
          <div className="extraction-bar-inner">
            {!document ? (
              <div className="grid gap-6 lg:grid-cols-[minmax(0,0.48fr)_minmax(0,0.52fr)]">
                <section className="space-y-4">
                  <DocumentUploader onUploadComplete={handleUploadComplete} />
                  <ImportSourceTabs />
                </section>
                <section className="editorial-card flex flex-col justify-center p-6 sm:p-8">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-teal">
                    Workflow
                  </p>
                  <h2 className="mt-2 text-lg font-medium text-foreground">
                    Upload → Understand → Extract → Verify
                  </h2>
                  <ol className="mt-4 space-y-3 text-sm leading-6 text-text-secondary">
                    <li>
                      <span className="font-medium text-foreground">1.</span>{" "}
                      Upload a document to extract pages and detect structure.
                    </li>
                    <li>
                      <span className="font-medium text-foreground">2.</span>{" "}
                      Discover the document&apos;s actual schema — not static
                      presets.
                    </li>
                    <li>
                      <span className="font-medium text-foreground">3.</span>{" "}
                      Choose detected fields, tables, clauses, or contacts.
                    </li>
                    <li>
                      <span className="font-medium text-foreground">4.</span>{" "}
                      Verify results against source evidence, then review.
                    </li>
                  </ol>
                </section>
              </div>
            ) : (
              <div className="grid gap-5 lg:grid-cols-[minmax(280px,0.38fr)_minmax(0,0.62fr)]">
                <section className="space-y-4 lg:sticky lg:top-4 lg:self-start">
                  <DocumentOverview
                    document={document}
                    structureDetection={structureDetection}
                    contractAnalysis={contractAnalysis}
                    extraction={extraction}
                    extracting={extracting}
                    progress={progress}
                    elapsedSeconds={elapsedSeconds}
                    waking={waking}
                    onOpenProcessingDetails={() => setProcessingDrawerOpen(true)}
                    onReplaceDocument={() => {
                      setDocument(null);
                      setExtraction(null);
                      setPages([]);
                      setUniversalResult(null);
                      setTargetResult(null);
                      setTargetResultDurationMs(null);
                      setContractAnalysis(null);
                      setStructuredOutput(null);
                      setStructureDetection(null);
                      setSchemaDiscovery(null);
                      setSchemaDiscoveryError("");
                      setWorkflowError("");
                      setContractAnalysisError("");
                    }}
                    onViewResults={
                      contractAnalysis || universalResult || targetResult
                        ? () =>
                            (contractAnalysis
                              ? resultsWorkspaceRef
                              : targetResult
                                ? targetResultRef
                                : universalResultRef
                            ).current?.scrollIntoView({ behavior: "smooth" })
                        : undefined
                    }
                  />
                </section>

                <section className="min-w-0 space-y-5">
                  <AnalysisRequest
                    disabled={!extraction || extracting}
                    onAnalyze={handleAnalyze}
                    onExtractTargets={handleExtractTargets}
                    waking={waking}
                    extractionJob={targetExtractionJob}
                    onAddCustomField={handleAddCustomField}
                    onRenameCustomField={handleRenameCustomField}
                    onDeleteCustomField={handleDeleteCustomField}
                    targets={(schemaDiscovery?.targets ?? []).filter(
                      (target) =>
                        target.source !== "template" &&
                        target.source_examples.length > 0,
                    )}
                    documentFamily={schemaDiscovery?.document_family}
                    documentFamilyLabel={
                      schemaDiscovery?.document_family_label
                    }
                    documentFamilyConfidence={
                      schemaDiscovery?.document_family_confidence
                    }
                    schemaDiscovering={schemaDiscovering || extracting}
                    schemaDiscoveryError={schemaDiscoveryError}
                    onRetryDiscovery={() =>
                      document && runSchemaDiscovery(document.document_id)
                    }
                  />

                  {extraction && !contractAnalysis && (
                    <div className="editorial-card animate-fade-in p-6">
                      <p className="text-base font-medium text-foreground">
                        Document Intelligence
                      </p>
                      {schemaDiscovery &&
                        schemaDiscovery.document_family !== "unknown" && (
                          <p className="mt-1 text-xs text-text-secondary">
                            Detected: {schemaDiscovery.document_family_label}
                            {" · "}
                            {confidenceQualifier(
                              schemaDiscovery.document_family_confidence,
                            )}
                          </p>
                        )}
                      <p className="mt-2 text-sm leading-6 text-text-secondary">
                        Classify this document, extract structured metadata, and
                        detect related documents when present.
                      </p>

                      {analyzingContract && (
                        <div className="mt-4 flex items-center gap-2 rounded-xl border border-primary/15 bg-primary/5 px-3.5 py-2.5 text-xs text-text-secondary">
                          <span className="h-2 w-2 animate-pulse rounded-full bg-primary" />
                          {waking
                            ? "Waking processing service... this can take up to a minute after idle."
                            : ANALYZE_STAGE_MESSAGES[analyzeStageIndex]}
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
                        {analyzingContract
                          ? "Analyzing..."
                          : "Run Document Intelligence"}
                      </button>

                      {contractAnalysisError && (
                        <div className="mt-4 rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm text-danger">
                          {contractAnalysisError}
                        </div>
                      )}
                    </div>
                  )}

                  {contractAnalysis && extraction && (
                    <div className="editorial-card animate-fade-in p-6">
                      <p className="text-base font-medium text-foreground">
                        Ready for review
                      </p>
                      <ul className="mt-3 space-y-1 text-sm text-text-secondary">
                        <li>{extraction.pages_processed} pages processed</li>
                        <li>Document classified</li>
                        <li>Relationships analyzed</li>
                        <li>
                          {contractAnalysis.metadata_fields.length} metadata
                          fields extracted
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
                        The document was uploaded successfully, but page
                        extraction failed.
                      </p>
                      <div className="mt-3 flex flex-wrap items-center gap-3">
                        <button
                          type="button"
                          onClick={() => handleUploadComplete(document)}
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
            )}
          </div>
        </div>

        {document && targetResult && !contractAnalysis && (
          <div className="extraction-workspace -mx-[max(1.5rem,3vw)] mt-8">
            <div
              ref={targetResultRef}
              className="extraction-workspace-inner animate-fade-in"
            >
              <div className="flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-text-teal">
                    Source Verification
                  </p>
                  <p className="mt-1 text-lg font-medium text-foreground">
                    PDF + Results workspace
                  </p>
                  <p className="mt-1 max-w-2xl text-sm text-text-secondary">
                    Click any extracted value to jump to its page, highlight the
                    evidence, and Verify / Edit / Reject — this is the core
                    Data Agent experience.
                  </p>
                </div>
              </div>

              <div className="mt-4">
                <ExtractionSummaryBar result={targetResult} />
              </div>

              {/*
                Responsive strategy:
                - Desktop (lg+): side-by-side split, PDF pane sticky.
                - Tablet (sm-lg): stacked, both panels always visible —
                  no toggle needed, there's room for both.
                - Mobile (<sm): Results only; "View Source" opens the PDF
                  pane as a full-screen drawer. The pane is NEVER unmounted
                  (only hidden/fixed via CSS) so its render cache survives
                  opening and closing the drawer repeatedly.
              */}
              <div className="mt-4 grid gap-5 lg:grid-cols-[minmax(0,0.5fr)_minmax(0,0.5fr)]">
                <div
                  className={[
                    mobileSourceOpen
                      ? "fixed inset-0 z-50 overflow-y-auto bg-background p-4"
                      : "hidden",
                    "sm:static sm:z-auto sm:block sm:overflow-visible sm:bg-transparent sm:p-0",
                    "min-h-0 lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)] lg:self-start lg:overflow-hidden",
                  ].join(" ")}
                >
                  {mobileSourceOpen && (
                    <div className="mb-3 sm:hidden">
                      <button
                        type="button"
                        onClick={() => setMobileSourceOpen(false)}
                        className="btn-secondary w-full text-sm"
                      >
                        Close Source Preview
                      </button>
                    </div>
                  )}
                  <div className="overflow-hidden rounded-xl border border-border bg-surface">
                    <div className="border-b border-border bg-surface-soft px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                        Source PDF
                      </p>
                    </div>
                    <SourceVerificationPanel
                      documentId={document.document_id}
                      documentName={document.original_filename}
                      pageCount={document.page_count}
                      request={sourceRequest}
                    />
                  </div>
                </div>

                <div className="min-w-0">
                  <div className="mb-2">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
                      Extraction Results
                    </p>
                  </div>
                  <TargetResults
                    result={targetResult}
                    targets={(schemaDiscovery?.targets ?? []).filter(
                      (target) =>
                        target.source !== "template" &&
                        target.source_examples.length > 0,
                    )}
                    documentId={document.document_id}
                    documentName={document.original_filename}
                    status="complete"
                    processingDurationMs={targetResultDurationMs}
                    selectedResultId={sourceRequest?.id ?? null}
                    onViewSource={handleViewSource}
                  />
                </div>
              </div>
            </div>
          </div>
        )}

        {document && universalResult && !contractAnalysis && (
          <div className="extraction-workspace -mx-[max(1.5rem,3vw)] mt-8">
            <div
              ref={universalResultRef}
              className="extraction-bar-inner animate-fade-in"
            >
              <p className="text-base font-medium text-foreground">
                Extraction Result
              </p>
              <div className="mt-4">
                <UniversalResults result={universalResult} />
              </div>
            </div>
          </div>
        )}

        {contractAnalysis && document && (
          <div ref={resultsWorkspaceRef} className="mt-8">
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

      {document && (
        <ProcessingDetailsDrawer
          open={processingDrawerOpen}
          onClose={() => setProcessingDrawerOpen(false)}
          document={document}
          extraction={extraction}
          extracting={extracting}
          contractAnalyzed={Boolean(contractAnalysis)}
          progress={progress}
          elapsedSeconds={elapsedSeconds}
          waking={waking}
        />
      )}
    </>
  );
}
