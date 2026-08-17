import { CheckCircle2, Eye, PenLine, XCircle } from "lucide-react";

import ConfidenceBadge from "@/components/confidence-badge";
import type { SignatureResult } from "@/types/document";

interface SignatureListProps {
  signatures: SignatureResult[];
  onViewSource: (signature: SignatureResult) => void;
}

export default function SignatureList({
  signatures,
  onViewSource,
}: SignatureListProps) {
  if (signatures.length === 0) {
    return null;
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-2">
        <PenLine className="h-4 w-4 text-blue-600" />
        <h2 className="text-sm font-semibold text-slate-950">
          Signature Analysis
        </h2>
        <span className="text-xs text-slate-400">
          {signatures.length} found
        </span>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {signatures.map((signature, index) => (
          <div
            key={`${signature.party_name}-${index}`}
            className="rounded-xl border border-slate-200 bg-slate-50 p-4"
          >
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-semibold text-slate-900">
                {signature.party_name}
              </p>
              <ConfidenceBadge confidence={signature.confidence} />
            </div>

            <p className="mt-2 text-sm text-slate-800">
              {signature.signatory_name || "—"}
            </p>
            {signature.signatory_title && (
              <p className="text-xs text-slate-500">
                {signature.signatory_title}
              </p>
            )}

            <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
              <div>
                <span className="text-slate-400">Signed</span>
                <p
                  className={[
                    "mt-0.5 inline-flex items-center gap-1 font-medium",
                    signature.signed
                      ? "text-emerald-700"
                      : "text-slate-500",
                  ].join(" ")}
                >
                  {signature.signed ? (
                    <>
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      Yes
                    </>
                  ) : (
                    <>
                      <XCircle className="h-3.5 w-3.5" />
                      No
                    </>
                  )}
                </p>
              </div>

              <div>
                <span className="text-slate-400">
                  Signature Date
                </span>
                <p className="mt-0.5 font-medium text-slate-800">
                  {signature.signature_date || "—"}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => onViewSource(signature)}
              className="mt-3 inline-flex items-center gap-1.5 text-xs font-semibold text-blue-700 hover:text-blue-800"
            >
              <Eye className="h-3.5 w-3.5" />
              View Source (Page {signature.evidence.page_number})
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
