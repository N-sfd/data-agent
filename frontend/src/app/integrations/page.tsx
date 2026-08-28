"use client";

import { useState } from "react";
import Link from "next/link";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Copy,
  Database,
  ExternalLink,
  Layers,
  Play,
  RefreshCw,
  Send,
  Server,
  ShieldCheck,
  Workflow,
  Zap,
} from "lucide-react";

import ContentSection from "@/components/layout/ContentSection";
import PageHero from "@/components/layout/PageHero";

interface DryRunPayload {
  source_document_id: string;
  source_document: string;
  erp_target: string;
  generated_at: string;
  contract_header: {
    contract_number: string;
    solicitation_number: string;
    dodaac: string;
    cage_code: string;
    naics_code: string;
    effective_date: string;
    total_amount: string;
    status: string;
  };
  line_items: Array<{
    clin: string;
    description: string;
    qty: number;
    unit_price: string;
    total_net: string;
  }>;
  compliance: {
    far_clauses_count: number;
    verification_status: string;
    review_state: string;
  };
}

const SAMPLE_ORACLE_PAYLOAD: DryRunPayload = {
  source_document_id: "doc-w912hq-verified",
  source_document: "W912HQ24C0001_Award_Executed.pdf",
  erp_target: "Oracle Fusion Cloud Procurement (PO-REST-v11.13.18.05)",
  generated_at: new Date().toISOString(),
  contract_header: {
    contract_number: "W912HQ-24-C-0001",
    solicitation_number: "W912HQ-24-R-0001",
    dodaac: "W58RGZ",
    cage_code: "1ABC2",
    naics_code: "541512",
    effective_date: "2024-10-01",
    total_amount: "$500,000.00",
    status: "APPROVED_VERIFIED",
  },
  line_items: [
    {
      clin: "0001",
      description: "Enterprise IT Support & Architecture Services",
      qty: 1,
      unit_price: "$350,000.00",
      total_net: "$350,000.00",
    },
    {
      clin: "0002",
      description: "Cybersecurity & Information Assurance Support",
      qty: 1,
      unit_price: "$150,000.00",
      total_net: "$150,000.00",
    },
  ],
  compliance: {
    far_clauses_count: 14,
    verification_status: "Source Grounded · 100% Verified",
    review_state: "Accepted by Contract Officer",
  },
};

export default function IntegrationsPage() {
  const [dryRunRunning, setDryRunRunning] = useState(false);
  const [dryRunResult, setDryRunResult] = useState<{
    status: "success" | "idle";
    message: string;
    validationCode: string;
  } | null>(null);

  const [copied, setCopied] = useState(false);

  function executeOracleDryRun() {
    setDryRunRunning(true);
    setDryRunResult(null);

    setTimeout(() => {
      setDryRunRunning(false);
      setDryRunResult({
        status: "success",
        message:
          "Oracle Fusion Cloud ERP schema validation passed (0 schema errors, 2 CLIN lines matched, FAR compliance attached).",
        validationCode: "ORA-200-OK-SIMULATION",
      });
    }, 900);
  }

  function handleCopyPayload() {
    navigator.clipboard.writeText(JSON.stringify(SAMPLE_ORACLE_PAYLOAD, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <>
      <PageHero
        eyebrow="Enterprise Governance & Integration"
        title="Integration Center & Approved Data"
        description="Synchronize verified document intelligence, metadata, and extracted CLIN line items into downstream ERP, automation workflows, and enterprise databases."
      />

      <ContentSection>
        {/* Top summary stats */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="editorial-card p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Database className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-text-secondary">
                  Oracle ERP Cloud
                </p>
                <p className="text-base font-semibold text-foreground">
                  Dry-Run Active
                </p>
              </div>
            </div>
            <p className="mt-3 text-xs text-text-muted">
              v11.13.18.05 · Purchase Orders & Contract Lines
            </p>
          </div>

          <div className="editorial-card p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-purple/10 text-accent-purple">
                <Workflow className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-text-secondary">
                  n8n Automation
                </p>
                <p className="text-base font-semibold text-foreground">
                  Webhook Ready
                </p>
              </div>
            </div>
            <p className="mt-3 text-xs text-text-muted">
              Triggers on human review accept & compliance flags
            </p>
          </div>

          <div className="editorial-card p-5">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-success/10 text-success">
                <ShieldCheck className="h-5 w-5" />
              </div>
              <div>
                <p className="text-xs uppercase tracking-wider text-text-secondary">
                  Data Provenance
                </p>
                <p className="text-base font-semibold text-foreground">
                  100% Source Grounded
                </p>
              </div>
            </div>
            <p className="mt-3 text-xs text-text-muted">
              Every exported field retains source page evidence
            </p>
          </div>
        </div>

        {/* Oracle Fusion Cloud Section */}
        <div className="mt-8 rounded-2xl border border-border bg-surface p-6 sm:p-8 shadow-sm">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-border/80 pb-6">
            <div>
              <div className="flex items-center gap-2">
                <span className="rounded bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary">
                  ERP Destination
                </span>
                <span className="text-xs text-text-muted">PO REST API</span>
              </div>
              <h2 className="mt-2 text-xl font-bold text-foreground">
                Oracle Fusion Cloud ERP Export
              </h2>
              <p className="mt-1 text-xs text-text-secondary">
                Generate and validate purchase order line item payloads from verified contract extractions.
              </p>
            </div>

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={executeOracleDryRun}
                disabled={dryRunRunning}
                className="btn-primary inline-flex items-center gap-2 text-xs font-semibold"
              >
                {dryRunRunning ? (
                  <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Play className="h-3.5 w-3.5" />
                )}
                {dryRunRunning ? "Validating Schema..." : "Run Dry-Run Simulation"}
              </button>
            </div>
          </div>

          {dryRunResult && (
            <div className="mt-6 rounded-xl border border-success/30 bg-success/5 p-4 text-xs">
              <div className="flex items-center gap-2 font-semibold text-success">
                <CheckCircle2 className="h-4 w-4" />
                {dryRunResult.validationCode}: {dryRunResult.message}
              </div>
            </div>
          )}

          {/* Payload preview */}
          <div className="mt-6">
            <div className="flex items-center justify-between pb-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-text-secondary">
                Simulated Oracle Payload (JSON)
              </span>
              <button
                type="button"
                onClick={handleCopyPayload}
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                <Copy className="h-3.5 w-3.5" />
                {copied ? "Copied!" : "Copy Payload"}
              </button>
            </div>
            <pre className="max-h-72 overflow-auto rounded-xl border border-border bg-surface-soft p-4 text-xs font-mono text-foreground">
              {JSON.stringify(SAMPLE_ORACLE_PAYLOAD, null, 2)}
            </pre>
          </div>
        </div>

        {/* n8n Automation and REST Webhooks */}
        <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* n8n */}
          <div className="rounded-2xl border border-border bg-surface p-6">
            <div className="flex items-center gap-2">
              <Workflow className="h-5 w-5 text-accent-purple" />
              <h3 className="text-base font-bold text-foreground">
                n8n Workflow Webhooks
              </h3>
            </div>
            <p className="mt-2 text-xs text-text-secondary">
              Broadcast verified extraction events directly into n8n canvas nodes to trigger notifications in Slack, Teams, or ticketing systems.
            </p>

            <div className="mt-5 space-y-3">
              <div className="rounded-xl border border-border bg-surface-soft p-3">
                <p className="text-[11px] font-semibold uppercase text-text-muted">
                  Webhook Event Endpoint
                </p>
                <code className="mt-1 block text-xs font-mono text-foreground">
                  POST /api/webhooks/n8n/document-approved
                </code>
              </div>

              <div className="flex items-center justify-between text-xs text-text-muted">
                <span>Supported events:</span>
                <span className="font-mono text-text-secondary">
                  document.verified, field.edited, clause.flagged
                </span>
              </div>
            </div>
          </div>

          {/* REST API & Export */}
          <div className="rounded-2xl border border-border bg-surface p-6">
            <div className="flex items-center gap-2">
              <Server className="h-5 w-5 text-primary" />
              <h3 className="text-base font-bold text-foreground">
                Enterprise REST API
              </h3>
            </div>
            <p className="mt-2 text-xs text-text-secondary">
              Direct programmatic access to verified documents, structured tables, and cross-contract field aggregations.
            </p>

            <div className="mt-5 space-y-3">
              <div className="flex items-center justify-between rounded-xl border border-border bg-surface-soft p-3">
                <div>
                  <p className="text-xs font-semibold text-foreground">
                    API Authentication
                  </p>
                  <p className="text-[11px] text-text-muted">
                    Bearer token & API-key signing
                  </p>
                </div>
                <Link
                  href="/api-keys"
                  className="btn-secondary text-xs px-3 py-1.5"
                >
                  Manage Keys
                </Link>
              </div>

              <div className="flex items-center justify-between text-xs text-text-muted">
                <span>Documentation:</span>
                <a
                  href="/docs"
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-primary hover:underline"
                >
                  Interactive OpenAPI (Swagger)
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            </div>
          </div>
        </div>

        {/* Upstream Cloud Storage Sources */}
        <div className="mt-8 rounded-2xl border border-border/80 bg-surface-soft/40 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-semibold text-foreground">
                Cloud Repository Ingestion Sources
              </h4>
              <p className="text-xs text-text-muted">
                Direct continuous syncing from cloud folders into the Data Agent processing queue.
              </p>
            </div>
            <span className="rounded-full bg-border/80 px-2.5 py-0.5 text-[11px] font-medium text-text-muted">
              Enterprise Add-on (Roadmap)
            </span>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded-xl border border-border bg-surface p-4 text-center opacity-75">
              <p className="text-xs font-semibold text-foreground">SharePoint / OneDrive</p>
              <p className="mt-1 text-[11px] text-text-muted">Microsoft Graph Ingest</p>
              <span className="mt-2 inline-block rounded bg-surface-soft px-2 py-0.5 text-[10px] text-text-muted">
                Coming Soon
              </span>
            </div>

            <div className="rounded-xl border border-border bg-surface p-4 text-center opacity-75">
              <p className="text-xs font-semibold text-foreground">Google Drive</p>
              <p className="mt-1 text-[11px] text-text-muted">Workspace Drive Connector</p>
              <span className="mt-2 inline-block rounded bg-surface-soft px-2 py-0.5 text-[10px] text-text-muted">
                Coming Soon
              </span>
            </div>

            <div className="rounded-xl border border-border bg-surface p-4 text-center opacity-75">
              <p className="text-xs font-semibold text-foreground">Amazon S3</p>
              <p className="mt-1 text-[11px] text-text-muted">Bucket Event SQS Ingest</p>
              <span className="mt-2 inline-block rounded bg-surface-soft px-2 py-0.5 text-[10px] text-text-muted">
                Coming Soon
              </span>
            </div>
          </div>
        </div>
      </ContentSection>
    </>
  );
}
