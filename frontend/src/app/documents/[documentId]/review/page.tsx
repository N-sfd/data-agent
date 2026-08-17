"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  PenLine,
  ScrollText,
  Table2,
} from "lucide-react";

import ClauseList from "@/components/clause-list";
import ExportMenu from "@/components/export-menu";
import PdfPageViewer from "@/components/pdf-page-viewer";
import RateCardTable from "@/components/rate-card-table";
import ReviewFieldList from "@/components/review-field-list";
import SignatureList from "@/components/signature-list";
import {
  acceptAllMetadataFields,
  extractClauses,
  extractSignatures,
  extractTables,
  getClauses,
  getContractAnalysis,
  getDocument,
  getPageRender,
  getSignatures,
  reviewMetadataField,
} from "@/lib/documents";
import type {
  ClauseResult,
  ContractAnalysisResult,
  MetadataField,
  NormalizedTable,
  PageRender,
  ReviewAction,
  SignatureResult,
  UploadedDocument,
} from "@/types/document";

interface ReviewPageProps {
  params: Promise<{ documentId: string }>;
}

interface ActiveSource {
  pageNumber: number;
  sourceText: string;
}

export default function ReviewWorkspacePage({
  params,
}: ReviewPageProps) {
  const { documentId } = use(params);

  const [document, setDocument] =
    useState<UploadedDocument | null>(null);
  const [analysis, setAnalysis] =
    useState<ContractAnalysisResult | null>(null);
  const [loadError, setLoadError] = useState("");

  const [reviewerName, setReviewerName] = useState("Asif Khan");

  const [activeFieldKey, setActiveFieldKey] =
    useState<string | null>(null);
  const [activeSource, setActiveSource] =
    useState<ActiveSource | null>(null);
  const [pageRender, setPageRender] =
    useState<PageRender | null>(null);
  const [renderLoading, setRenderLoading] = useState(false);
  const [renderError, setRenderError] = useState("");

  const [reviewingKey, setReviewingKey] =
    useState<string | null>(null);
  const [acceptingAll, setAcceptingAll] = useState(false);

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
        ] = await Promise.all([
          getDocument(documentId),
          getContractAnalysis(documentId),
          getClauses(documentId).catch(() => null),
          getSignatures(documentId).catch(() => null),
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

        const firstField = analysisResult.metadata_fields[0];

        if (firstField) {
          setActiveFieldKey(firstField.field_key);
          setActiveSource({
            pageNumber: firstField.evidence.page_number,
            sourceText: firstField.evidence.source_text,
          });
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
    if (!activeSource) {
      return;
    }

    const source = activeSource;
    let active = true;

    async function loadPage() {
      setRenderLoading(true);
      setRenderError("");

      try {
        const render = await getPageRender(
          documentId,
          source.pageNumber,
          source.sourceText,
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
  }, [activeSource, documentId]);

  function handleSelectField(field: MetadataField) {
    setActiveFieldKey(field.field_key);
    setActiveSource({
      pageNumber: field.evidence.page_number,
      sourceText: field.evidence.source_text,
    });
  }

  function handleViewClauseSource(clause: ClauseResult) {
    setActiveFieldKey(null);
    setActiveSource({
      pageNumber: clause.evidence.page_number,
      sourceText: clause.evidence.source_text,
    });
  }

  function handleViewSignatureSource(signature: SignatureResult) {
    setActiveFieldKey(null);
    setActiveSource({
      pageNumber: signature.evidence.page_number,
      sourceText: signature.evidence.source_text,
    });
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

          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-700">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Extraction: Complete
          </span>
        </div>
      </div>

      <div className="grid flex-1 grid-cols-2 overflow-hidden">
        <div className="flex flex-col overflow-hidden border-r border-slate-200">
          <div className="flex-1 overflow-hidden">
            <PdfPageViewer
              render={pageRender}
              loading={renderLoading}
              error={renderError}
            />
          </div>

          <div className="shrink-0 space-y-3 overflow-y-auto border-t border-slate-200 bg-slate-50 p-4">
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={handleExtractClauses}
                disabled={extractingClauses}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <ScrollText className="h-3.5 w-3.5" />
                {extractingClauses
                  ? "Extracting Clauses..."
                  : "Extract Clauses"}
              </button>

              <button
                type="button"
                onClick={handleExtractTables}
                disabled={extractingTables}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <Table2 className="h-3.5 w-3.5" />
                {extractingTables
                  ? "Extracting Tables..."
                  : "Extract Tables"}
              </button>

              <button
                type="button"
                onClick={handleExtractSignatures}
                disabled={extractingSignatures}
                className="inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                <PenLine className="h-3.5 w-3.5" />
                {extractingSignatures
                  ? "Extracting Signatures..."
                  : "Extract Signatures"}
              </button>
            </div>

            {clausesError && (
              <p className="text-xs text-red-700">
                {clausesError}
              </p>
            )}
            {tablesError && (
              <p className="text-xs text-red-700">
                {tablesError}
              </p>
            )}
            {signaturesError && (
              <p className="text-xs text-red-700">
                {signaturesError}
              </p>
            )}

            {clauses.length > 0 && (
              <ClauseList
                clauses={clauses}
                onViewSource={handleViewClauseSource}
              />
            )}

            {tables.length > 0 && (
              <RateCardTable tables={tables} />
            )}

            {signatures.length > 0 && (
              <SignatureList
                signatures={signatures}
                onViewSource={handleViewSignatureSource}
              />
            )}
          </div>
        </div>

        <div className="overflow-hidden">
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
  );
}
