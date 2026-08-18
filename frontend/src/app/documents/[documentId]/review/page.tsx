"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BadgeCheck } from "lucide-react";

import ContractRelationshipsTree from "@/components/contract-relationships-tree";
import DocumentProfileCard from "@/components/document-profile-card";
import ExportMenu from "@/components/export-menu";
import ExtractionWorkspace from "@/components/extraction-workspace";
import PdfPageViewer from "@/components/pdf-page-viewer";
import PdfToolbar, { type SearchMatch } from "@/components/pdf-toolbar";
import PipelineStrip from "@/components/pipeline-strip";
import RelationshipCard from "@/components/relationship-card";
import ReviewFieldList from "@/components/review-field-list";
import {
  acceptAllMetadataFields,
  approveDocument,
  confirmRelationship,
  extractClauses,
  extractSignatures,
  extractTables,
  getChildRelationships,
  getClauses,
  getContractAnalysis,
  getDocument,
  getDocumentPages,
  getPageRender,
  getSignatures,
  reviewMetadataField,
} from "@/lib/documents";
import type {
  ChildRelationship,
  ClauseResult,
  ContractAnalysisResult,
  DocumentPage,
  MetadataField,
  NormalizedTable,
  PageRender,
  RelationshipAction,
  ReviewAction,
  SignatureResult,
  UploadedDocument,
} from "@/types/document";

interface ReviewPageProps {
  params: Promise<{ documentId: string }>;
}

export default function ReviewWorkspacePage({
  params,
}: ReviewPageProps) {
  const { documentId } = use(params);

  const [document, setDocument] =
    useState<UploadedDocument | null>(null);
  const [analysis, setAnalysis] =
    useState<ContractAnalysisResult | null>(null);
  const [children, setChildren] = useState<ChildRelationship[]>([]);
  const [loadError, setLoadError] = useState("");

  const [reviewerName, setReviewerName] = useState("Consult America");

  const [activeFieldKey, setActiveFieldKey] =
    useState<string | null>(null);

  const [currentPage, setCurrentPage] = useState(1);
  const [highlightText, setHighlightText] = useState<string | null>(
    null,
  );
  const [pageRender, setPageRender] =
    useState<PageRender | null>(null);
  const [renderLoading, setRenderLoading] = useState(false);
  const [renderError, setRenderError] = useState("");

  const [zoom, setZoom] = useState(1);
  const [rotation, setRotation] = useState<0 | 90 | 180 | 270>(0);

  const [documentPages, setDocumentPages] = useState<
    DocumentPage[] | null
  >(null);
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<
    SearchMatch[] | null
  >(null);
  const [lastQuery, setLastQuery] = useState("");

  const [reviewingKey, setReviewingKey] =
    useState<string | null>(null);
  const [acceptingAll, setAcceptingAll] = useState(false);

  const [relationshipBusy, setRelationshipBusy] = useState(false);

  const [approving, setApproving] = useState(false);
  const [approveError, setApproveError] = useState("");

  const [clauses, setClauses] = useState<ClauseResult[]>([]);
  const [extractingClauses, setExtractingClauses] =
    useState(false);
  const [clausesError, setClausesError] = useState("");

  const [tables, setTables] = useState<NormalizedTable[]>([]);
  const [extractingTables, setExtractingTables] =
    useState(false);
  const [tablesError, setTablesError] = useState("");

  const [signatures, setSignatures] = useState<
    SignatureResult[]
  >([]);
  const [extractingSignatures, setExtractingSignatures] =
    useState(false);
  const [signaturesError, setSignaturesError] = useState("");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        const [
          documentResult,
          analysisResult,
          clausesResult,
          signaturesResult,
          childrenResult,
        ] = await Promise.all([
          getDocument(documentId),
          getContractAnalysis(documentId),
          getClauses(documentId).catch(() => null),
          getSignatures(documentId).catch(() => null),
          getChildRelationships(documentId).catch(() => null),
        ]);

        if (!active) return;

        setDocument(documentResult);
        setAnalysis(analysisResult);

        if (clausesResult) {
          setClauses(clausesResult.clauses);
        }

        if (signaturesResult) {
          setSignatures(signaturesResult.signatures);
        }

        if (childrenResult) {
          setChildren(childrenResult.children);
        }

        const firstField = analysisResult.metadata_fields[0];

        if (firstField) {
          setActiveFieldKey(firstField.field_key);
          setCurrentPage(firstField.evidence.page_number);
          setHighlightText(firstField.evidence.source_text);
        }
      } catch (error) {
        if (!active) return;

        setLoadError(
          error instanceof Error
            ? error.message
            : "Unable to load this document's analysis.",
        );
      }
    }

    load();

    return () => {
      active = false;
    };
  }, [documentId]);

  useEffect(() => {
    let active = true;

    async function loadPage() {
      setRenderLoading(true);
      setRenderError("");

      try {
        const render = await getPageRender(
          documentId,
          currentPage,
          highlightText ?? undefined,
        );

        if (active) {
          setPageRender(render);
        }
      } catch (error) {
        if (active) {
          setRenderError(
            error instanceof Error
              ? error.message
              : "Unable to render this page.",
          );
        }
      } finally {
        if (active) {
          setRenderLoading(false);
        }
      }
    }

    loadPage();

    return () => {
      active = false;
    };
  }, [currentPage, highlightText, documentId]);

  function handleSelectField(field: MetadataField) {
    setActiveFieldKey(field.field_key);
    setCurrentPage(field.evidence.page_number);
    setHighlightText(field.evidence.source_text);
  }

  function handleViewClauseSource(clause: ClauseResult) {
    setActiveFieldKey(null);
    setCurrentPage(clause.evidence.page_number);
    setHighlightText(clause.evidence.source_text);
  }

  function handleViewSignatureSource(signature: SignatureResult) {
    setActiveFieldKey(null);
    setCurrentPage(signature.evidence.page_number);
    setHighlightText(signature.evidence.source_text);
  }

  function handlePageChange(page: number) {
    if (!document || page < 1 || page > document.page_count) {
      return;
    }

    setActiveFieldKey(null);
    setHighlightText(null);
    setCurrentPage(page);
  }

  function handleRotate() {
    setRotation((current) =>
      current === 270 ? 0 : ((current + 90) as 0 | 90 | 180 | 270),
    );
  }

  async function handleSearch(query: string) {
    setSearching(true);
    setLastQuery(query);

    try {
      let pages = documentPages;

      if (!pages) {
        pages = await getDocumentPages(documentId);
        setDocumentPages(pages);
      }

      const needle = query.toLowerCase();

      const results: SearchMatch[] = pages
        .map((page) => {
          const haystack = page.final_text.toLowerCase();
          let count = 0;
          let index = haystack.indexOf(needle);

          while (index !== -1) {
            count += 1;
            index = haystack.indexOf(needle, index + needle.length);
          }

          return { pageNumber: page.page_number, matches: count };
        })
        .filter((result) => result.matches > 0);

      setSearchResults(results);
    } catch {
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  function handleJumpToResult(pageNumber: number) {
    setActiveFieldKey(null);
    setCurrentPage(pageNumber);
    setHighlightText(lastQuery);
  }

  async function handleReviewField(
    fieldKey: string,
    action: ReviewAction,
    value?: string,
  ) {
    if (!reviewerName.trim()) {
      return;
    }

    setReviewingKey(fieldKey);

    try {
      const updated = await reviewMetadataField(
        documentId,
        fieldKey,
        action,
        reviewerName.trim(),
        value,
      );

      setAnalysis((current) => {
        if (!current) return current;

        return {
          ...current,
          metadata_fields: current.metadata_fields.map(
            (field) =>
              field.field_key === fieldKey ? updated : field,
          ),
        };
      });
    } catch {
      // Non-fatal; the row simply stays actionable for retry.
    } finally {
      setReviewingKey(null);
    }
  }

  async function handleAcceptAll() {
    if (!reviewerName.trim()) {
      return;
    }

    setAcceptingAll(true);

    try {
      const updated = await acceptAllMetadataFields(
        documentId,
        reviewerName.trim(),
      );
      const byKey = new Map(
        updated.map((field) => [field.field_key, field]),
      );

      setAnalysis((current) => {
        if (!current) return current;

        return {
          ...current,
          metadata_fields: current.metadata_fields.map(
            (field) => byKey.get(field.field_key) ?? field,
          ),
        };
      });
    } catch {
      // Non-fatal.
    } finally {
      setAcceptingAll(false);
    }
  }

  async function handleRelationshipAction(
    action: RelationshipAction,
  ) {
    if (!analysis?.relationship) {
      return;
    }

    setRelationshipBusy(true);

    try {
      const result = await confirmRelationship(documentId, action);

      setAnalysis((current) => {
        if (!current) return current;

        return {
          ...current,
          relationship: result.relationship,
        };
      });
    } catch {
      // Non-fatal; the card simply stays actionable for retry.
    } finally {
      setRelationshipBusy(false);
    }
  }

  function handleChildrenChanged(updated: ChildRelationship[]) {
    setChildren(updated);
  }

  async function handleApprove() {
    if (!reviewerName.trim()) {
      return;
    }

    setApproving(true);
    setApproveError("");

    try {
      const result = await approveDocument(
        documentId,
        reviewerName.trim(),
      );

      setDocument((current) =>
        current
          ? {
              ...current,
              approved_by: result.approved_by,
              approved_at: result.approved_at,
            }
          : current,
      );
    } catch (error) {
      setApproveError(
        error instanceof Error
          ? error.message
          : "Unable to approve this document.",
      );
    } finally {
      setApproving(false);
    }
  }

  async function handleExtractClauses() {
    setExtractingClauses(true);
    setClausesError("");

    try {
      const result = await extractClauses(documentId);
      setClauses(result.clauses);
    } catch (error) {
      setClausesError(
        error instanceof Error
          ? error.message
          : "Clause extraction failed.",
      );
    } finally {
      setExtractingClauses(false);
    }
  }

  async function handleExtractTables() {
    setExtractingTables(true);
    setTablesError("");

    try {
      const result = await extractTables(documentId);
      setTables(result.tables);
    } catch (error) {
      setTablesError(
        error instanceof Error
          ? error.message
          : "Table extraction failed.",
      );
    } finally {
      setExtractingTables(false);
    }
  }

  async function handleExtractSignatures() {
    setExtractingSignatures(true);
    setSignaturesError("");

    try {
      const result = await extractSignatures(documentId);
      setSignatures(result.signatures);
    } catch (error) {
      setSignaturesError(
        error instanceof Error
          ? error.message
          : "Signature extraction failed.",
      );
    } finally {
      setExtractingSignatures(false);
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto max-w-2xl px-6 py-16 text-center">
        <p className="text-sm font-medium text-red-700">
          {loadError}
        </p>

        <Link
          href="/"
          className="mt-4 inline-flex items-center gap-1.5 text-sm font-semibold text-blue-700 hover:text-blue-800"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to dashboard
        </Link>
      </div>
    );
  }

  if (!document || !analysis) {
    return (
      <div className="flex h-[calc(100vh-4rem)] items-center justify-center text-sm text-slate-500">
        Loading review workspace...
      </div>
    );
  }

  const contractNumber = analysis.metadata_fields.find(
    (field) => field.field_key === "contract_number",
  )?.value;

  const fieldsExtracted = analysis.metadata_fields.length > 0;
  const humanReviewComplete =
    fieldsExtracted &&
    analysis.metadata_fields.every(
      (field) => field.review_status !== "pending",
    );
  const approved = Boolean(document.approved_at);

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-slate-200 bg-white px-6 py-3">
        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="text-slate-400 hover:text-slate-700"
            aria-label="Back to dashboard"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>

          <p className="text-sm font-semibold text-slate-950">
            {contractNumber ?? document.original_filename}
          </p>
        </div>

        <PipelineStrip
          classified={Boolean(analysis.classification?.document_type)}
          fieldsExtracted={fieldsExtracted}
          humanReviewComplete={humanReviewComplete}
          approved={approved}
        />

        <div className="flex items-center gap-4">
          <ExportMenu
            documentId={documentId}
            filename={document.original_filename.replace(
              /\.[^.]+$/,
              "",
            )}
            fields={analysis.metadata_fields}
          />

          <label className="flex items-center gap-2 text-xs text-slate-500">
            Reviewing as
            <input
              type="text"
              value={reviewerName}
              onChange={(event) =>
                setReviewerName(event.target.value)
              }
              className="w-36 rounded-lg border border-slate-300 px-2 py-1 text-xs text-slate-800"
            />
          </label>

          {approved ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
              <BadgeCheck className="h-3.5 w-3.5" />
              Approved by {document.approved_by}
            </span>
          ) : (
            <button
              type="button"
              onClick={handleApprove}
              disabled={!humanReviewComplete || approving}
              title={
                humanReviewComplete
                  ? undefined
                  : "Every extracted field must be reviewed before this document can be approved."
              }
              className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 px-3 py-1 text-xs font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-slate-200 disabled:text-slate-400"
            >
              <BadgeCheck className="h-3.5 w-3.5" />
              {approving ? "Approving..." : "Approve Document"}
            </button>
          )}
        </div>
      </div>

      {approveError && (
        <p className="shrink-0 border-b border-red-100 bg-red-50 px-6 py-1.5 text-xs text-red-700">
          {approveError}
        </p>
      )}

      <div className="grid flex-1 grid-cols-2 overflow-hidden">
        <div className="flex flex-col overflow-hidden border-r border-slate-200">
          <PdfToolbar
            currentPage={currentPage}
            pageCount={document.page_count}
            onPageChange={handlePageChange}
            zoom={zoom}
            onZoomChange={setZoom}
            onRotate={handleRotate}
            onSearch={handleSearch}
            searching={searching}
            searchResults={searchResults}
            onJumpToResult={handleJumpToResult}
          />

          <div className="flex-1 overflow-hidden">
            <PdfPageViewer
              render={pageRender}
              loading={renderLoading}
              error={renderError}
              zoom={zoom}
              rotation={rotation}
            />
          </div>

          <div className="shrink-0 max-h-[45vh] overflow-y-auto border-t border-slate-200 bg-slate-50 p-4">
            <ExtractionWorkspace
              clauses={clauses}
              extractingClauses={extractingClauses}
              clausesError={clausesError}
              onExtractClauses={handleExtractClauses}
              onViewClauseSource={handleViewClauseSource}
              tables={tables}
              extractingTables={extractingTables}
              tablesError={tablesError}
              onExtractTables={handleExtractTables}
              signatures={signatures}
              extractingSignatures={extractingSignatures}
              signaturesError={signaturesError}
              onExtractSignatures={handleExtractSignatures}
              onViewSignatureSource={handleViewSignatureSource}
            />
          </div>
        </div>

        <div className="flex h-full flex-col overflow-hidden">
          <div className="max-h-[45vh] shrink-0 space-y-4 overflow-y-auto p-4 pb-0">
            <DocumentProfileCard
              classification={analysis.classification}
            />

            {analysis.relationship && (
              <RelationshipCard
                relationship={analysis.relationship}
                onConfirm={() =>
                  handleRelationshipAction("confirm")
                }
                onReject={() => handleRelationshipAction("reject")}
                busy={relationshipBusy}
              />
            )}

            {children.length > 0 && (
              <ContractRelationshipsTree
                rootLabel={contractNumber ?? document.original_filename}
                childRelationships={children}
                onChanged={handleChildrenChanged}
              />
            )}
          </div>

          <div className="min-h-0 flex-1">
            <ReviewFieldList
              documentId={documentId}
              fields={analysis.metadata_fields}
              activeFieldKey={activeFieldKey}
              onSelectField={handleSelectField}
              onReviewField={handleReviewField}
              onAcceptAll={handleAcceptAll}
              reviewingKey={reviewingKey}
              acceptingAll={acceptingAll}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
