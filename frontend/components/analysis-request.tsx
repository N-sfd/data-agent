"use client";

import { ArrowRight, Search } from "lucide-react";
import { useState } from "react";

interface AnalysisRequestProps {
  disabled?: boolean;
  waking?: boolean;

  onAnalyze: (
    instruction: string
  ) => Promise<void>;
}

type ExtractionType =
  | "field"
  | "table"
  | "contacts"
  | "obligations"
  | "custom";

interface ExtractionTarget {
  id: string;
  label: string;
  prompt: string;
}

interface ExtractionTypeDefinition {
  label: string;
  targets: ExtractionTarget[];
}

const EXTRACTION_TAXONOMY: Record<
  ExtractionType,
  ExtractionTypeDefinition
> = {
  field: {
    label: "Field",
    targets: [
      {
        id: "contract_number",
        label: "Contract Number",
        prompt: "Extract the contract number.",
      },
      {
        id: "contract_title",
        label: "Contract Title",
        prompt: "Extract the contract title.",
      },
      {
        id: "supplier",
        label: "Supplier",
        prompt: "Extract the supplier name.",
      },
      {
        id: "customer",
        label: "Customer",
        prompt: "Extract the customer name.",
      },
      {
        id: "effective_date",
        label: "Effective Date",
        prompt: "Extract the effective date of the contract.",
      },
      {
        id: "expiration_date",
        label: "Expiration Date",
        prompt: "Extract the expiration date of the contract.",
      },
      {
        id: "award_date",
        label: "Award Date",
        prompt: "Extract the contract award date.",
      },
      {
        id: "contract_value",
        label: "Contract Value",
        prompt: "Extract the total contract value.",
      },
      {
        id: "payment_terms",
        label: "Payment Terms",
        prompt: "Extract the payment terms.",
      },
      {
        id: "governing_law",
        label: "Governing Law",
        prompt: "Extract the governing law clause.",
      },
      {
        id: "naics_code",
        label: "NAICS Code",
        prompt: "Extract the NAICS code and size standard.",
      },
      {
        id: "contracting_officer",
        label: "Contracting Officer",
        prompt:
          "Extract the contracting officer's name and contact information.",
      },
    ],
  },
  table: {
    label: "Table",
    targets: [
      {
        id: "clins",
        label: "CLINs",
        prompt:
          "Extract all CLINs with quantities, unit prices, total prices, and descriptions.",
      },
      {
        id: "pricing_table",
        label: "Pricing Table",
        prompt:
          "Extract the full pricing table with all line items and amounts.",
      },
      {
        id: "rate_card",
        label: "Rate Card",
        prompt:
          "Extract the rate card with labor categories and hourly rates.",
      },
      {
        id: "payment_schedule",
        label: "Payment Schedule",
        prompt:
          "Extract the payment schedule with due dates and amounts.",
      },
      {
        id: "delivery_schedule",
        label: "Delivery Schedule",
        prompt:
          "Extract the delivery schedule with milestones and dates.",
      },
      {
        id: "line_items",
        label: "Line Items",
        prompt:
          "Extract all line items with descriptions, quantities, and prices.",
      },
      {
        id: "funding_table",
        label: "Funding Table",
        prompt:
          "Extract the funding table with allocations and amounts.",
      },
      {
        id: "milestones",
        label: "Milestones",
        prompt: "Extract all milestones with dates and deliverables.",
      },
    ],
  },
  contacts: {
    label: "Contacts",
    targets: [
      {
        id: "all_contacts",
        label: "All Contacts",
        prompt:
          "Extract all contacts mentioned in the document, including names, roles, emails, and phone numbers.",
      },
      {
        id: "names",
        label: "Names",
        prompt: "Extract every person's name mentioned in the document.",
      },
      {
        id: "emails",
        label: "Emails",
        prompt:
          "Find every email address in the document and identify the associated person or organization where possible.",
      },
      {
        id: "phone_numbers",
        label: "Phone Numbers",
        prompt:
          "Find every telephone number in the document and identify the associated person or organization where possible.",
      },
      {
        id: "addresses",
        label: "Addresses",
        prompt: "Extract all mailing addresses in the document.",
      },
      {
        id: "contracting_officer",
        label: "Contracting Officer",
        prompt:
          "Extract the contracting officer's name and contact information.",
      },
      {
        id: "cor_cotr",
        label: "COR / COTR",
        prompt: "Extract the COR/COTR name and contact information.",
      },
      {
        id: "signatories",
        label: "Signatories",
        prompt:
          "Extract the names and titles of all signatories on the document.",
      },
    ],
  },
  obligations: {
    label: "Obligations",
    targets: [
      {
        id: "payment_obligations",
        label: "Payment Obligations",
        prompt: "Extract all payment obligations and terms.",
      },
      {
        id: "delivery_obligations",
        label: "Delivery Obligations",
        prompt: "Extract all delivery obligations and deadlines.",
      },
      {
        id: "reporting_requirements",
        label: "Reporting Requirements",
        prompt:
          "Extract all reporting requirements and their frequency.",
      },
      {
        id: "renewal_obligations",
        label: "Renewal Obligations",
        prompt: "Extract all renewal obligations and notice periods.",
      },
      {
        id: "notice_requirements",
        label: "Notice Requirements",
        prompt:
          "Extract all notice requirements, including required lead time and delivery method.",
      },
      {
        id: "insurance_requirements",
        label: "Insurance Requirements",
        prompt:
          "Extract all insurance requirements, including coverage types and minimum amounts.",
      },
      {
        id: "compliance_requirements",
        label: "Compliance Requirements",
        prompt: "Extract all compliance requirements referenced in the document.",
      },
      {
        id: "performance_obligations",
        label: "Performance Obligations",
        prompt: "Extract all performance obligations and standards.",
      },
    ],
  },
  custom: {
    label: "Custom",
    targets: [
      { id: "custom_field", label: "Custom Field", prompt: "" },
      { id: "custom_table", label: "Custom Table", prompt: "" },
      { id: "custom_question", label: "Custom Question", prompt: "" },
      {
        id: "custom_extraction_instruction",
        label: "Custom Extraction Instruction",
        prompt: "",
      },
    ],
  },
};

const EXTRACTION_TYPES = Object.keys(
  EXTRACTION_TAXONOMY,
) as ExtractionType[];

export default function AnalysisRequest({
  disabled = false,
  waking = false,
  onAnalyze,
}: AnalysisRequestProps) {
  const [extractionType, setExtractionType] =
    useState<ExtractionType>("field");
  const [targetId, setTargetId] = useState(
    EXTRACTION_TAXONOMY.field.targets[0].id,
  );
  const [instruction, setInstruction] = useState(
    EXTRACTION_TAXONOMY.field.targets[0].prompt,
  );
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  const targets = EXTRACTION_TAXONOMY[extractionType].targets;

  function handleTypeChange(nextType: ExtractionType) {
    const firstTarget = EXTRACTION_TAXONOMY[nextType].targets[0];

    setExtractionType(nextType);
    setTargetId(firstTarget.id);
    setInstruction(firstTarget.prompt);
  }

  function handleTargetChange(nextTargetId: string) {
    const target = targets.find((item) => item.id === nextTargetId);

    if (!target) {
      return;
    }

    setTargetId(target.id);
    setInstruction(target.prompt);
  }

  async function continueAnalysis() {
    if (!instruction.trim()) {
      return;
    }

    setAnalyzing(true);
    setError("");

    try {
      await onAnalyze(instruction.trim());
    } catch (analysisError) {
      setError(
        analysisError instanceof Error
          ? analysisError.message
          : "Analysis failed.",
      );
    } finally {
      setAnalyzing(false);
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50">
          <Search className="h-5 w-5 text-blue-600" />
        </div>

        <div>
          <h2 className="text-lg font-semibold text-slate-950">
            What do you want to know or extract?
          </h2>

          <p className="mt-1 text-sm leading-6 text-slate-500">
            Ask for fields, tables, contacts, obligations,
            or any custom information in the document.
          </p>
        </div>
      </div>

      <div className="mt-5 grid gap-4 sm:grid-cols-2">
        <label className="block text-xs font-medium text-slate-500">
          Extraction Type
          <select
            value={extractionType}
            disabled={disabled || analyzing}
            onChange={(event) =>
              handleTypeChange(event.target.value as ExtractionType)
            }
            className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
          >
            {EXTRACTION_TYPES.map((type) => (
              <option key={type} value={type}>
                {EXTRACTION_TAXONOMY[type].label}
              </option>
            ))}
          </select>
        </label>

        <label className="block text-xs font-medium text-slate-500">
          Extraction Target
          <select
            value={targetId}
            disabled={disabled || analyzing}
            onChange={(event) =>
              handleTargetChange(event.target.value)
            }
            className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
          >
            {targets.map((target) => (
              <option key={target.id} value={target.id}>
                {target.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="mt-5 block text-xs font-medium text-slate-500">
        Instruction
        <textarea
          value={instruction}
          disabled={disabled || analyzing}
          onChange={(event) =>
            setInstruction(event.target.value)
          }
          rows={5}
          placeholder="Describe what to extract, or pick a type and target above to prefill this."
          className="mt-1.5 w-full resize-none rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
        />
      </label>

      <div className="mt-4 flex items-center gap-2">
        <span className="text-xs font-medium text-slate-500">
          Extraction Mode
        </span>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
          {EXTRACTION_TAXONOMY[extractionType].label}
        </span>
      </div>

      <button
        type="button"
        disabled={
          disabled ||
          analyzing ||
          !instruction.trim()
        }
        onClick={continueAnalysis}
        className="mt-5 inline-flex items-center gap-2 rounded-xl bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
      >
        {analyzing
          ? "Analyzing..."
          : "Analyze Document"}

        {!analyzing && (
          <ArrowRight className="h-4 w-4" />
        )}
      </button>

      {analyzing && waking && (
        <div className="mt-4 rounded-xl bg-slate-50 p-3 text-sm text-slate-600">
          Waking processing service... this can take up to a minute
          after a deploy.
        </div>
      )}

      {error && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}
