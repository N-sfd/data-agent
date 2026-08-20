"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ExternalLink, Loader2 } from "lucide-react";

import { searchDocuments } from "@/lib/documents";
import type { ExplorerFieldKey } from "@/lib/field-schema";

interface ClickableFieldValueProps {
  fieldKey: string;
  fieldLabel: string;
  value: string;
}

export default function ClickableFieldValue({
  fieldKey,
  fieldLabel,
  value,
}: ClickableFieldValueProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [matchCount, setMatchCount] = useState<number | null>(null);

  useEffect(() => {
    if (!open) return;

    let active = true;
    setLoading(true);

    searchDocuments({ q: value, limit: 1 })
      .then((result) => {
        if (active) setMatchCount(result.total);
      })
      .catch(() => {
        if (active) setMatchCount(0);
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [open, value]);

  const explorerHref = `/explorer?field=${encodeURIComponent(fieldKey)}&value=${encodeURIComponent(value)}`;
  const searchHref = `/search?q=${encodeURIComponent(value)}`;

  return (
    <div className="relative">
      <button
        type="button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((current) => !current);
        }}
        className="max-w-xs truncate text-left text-sm font-medium text-primary hover:underline"
      >
        {value}
      </button>

      {open && (
        <div
          className="absolute left-0 top-full z-30 mt-2 w-72 rounded-2xl border border-border bg-surface p-4 shadow-[var(--shadow-elevated)] animate-fade-in"
          onClick={(event) => event.stopPropagation()}
        >
          <p className="text-xs text-text-secondary">{fieldLabel}</p>
          <p className="mt-1 text-sm font-medium text-foreground">{value}</p>

          {loading ? (
            <div className="mt-3 flex items-center gap-2 text-xs text-text-secondary">
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Finding matching contracts...
            </div>
          ) : (
            <p className="mt-3 text-sm text-text-secondary">
              {matchCount ?? 0} matching contract
              {(matchCount ?? 0) === 1 ? "" : "s"}
            </p>
          )}

          <div className="mt-4 flex flex-col gap-2">
            <Link
              href={searchHref}
              className="btn-secondary justify-center py-2 text-xs"
            >
              View Contracts
            </Link>
            <Link
              href={explorerHref}
              className="inline-flex items-center justify-center gap-1 text-xs font-medium text-primary hover:underline"
            >
              Open in Field Explorer
              <ExternalLink className="h-3 w-3" />
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

export function isExplorerFieldKey(key: string): key is ExplorerFieldKey {
  return [
    "payment_terms",
    "governing_law",
    "contract_value",
    "effective_date",
    "expiration_date",
    "supplier",
    "customer",
    "counterparty",
    "contract_type",
    "contract_number",
    "contract_title",
    "renewal_date",
    "termination_rights",
    "liability_cap",
    "currency",
  ].includes(key);
}
