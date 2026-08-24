"use client";

import { ArrowRight, ChevronDown, ChevronRight, Search } from "lucide-react";
import { useState } from "react";

import type {
  StructureDetectionResult,
  UniversalExtractionResult,
} from "@/types/document";

interface AnalysisRequestProps {
  disabled?: boolean;
  waking?: boolean;
  structureDetection?: StructureDetectionResult | null;

  onAnalyze: (
    instruction: string,
  ) => Promise<UniversalExtractionResult>;
}

type ExtractionType =
  | "field"
  | "table"
  | "contacts"
  | "obligations"
  | "custom";

interface ExtractionTemplate {
  id: string;
  label: string;
  prompt: string;
}

interface ExtractionTypeDefinition {
  label: string;
  targets: ExtractionTemplate[];
}

// The static template library — not claims about what's in the
// current document, just generic starting points. Demoted to "More
// extraction options" whenever real detections are available.
const EXTRACTION_TEMPLATES: Record<
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
  EXTRACTION_TEMPLATES,
) as ExtractionType[];

interface DetectedOption {
  type: ExtractionType;
  key: string;
  label: string;
  prompt: string;
}

function pagesLabel(pages: number[]): string {
  if (pages.length <= 1) {
    return `page ${pages[0] ?? "?"}`;
  }

  return `pages ${pages.join(", ")}`;
}

function buildDetectedOptions(
  detection: StructureDetectionResult | null,
): DetectedOption[] {
  if (!detection) {
    return [];
  }

  const options: DetectedOption[] = [];

  for (const table of detection.detected_tables) {
    options.push({
      type: "table",
      key: `table:${table.key}`,
      label: table.label,
      prompt: `Extract the ${table.label} table (${pagesLabel(table.pages)}) with all rows and columns.`,
    });
  }

  for (const field of detection.detected_fields) {
    options.push({
      type: "field",
      key: `field:${field.key}`,
      label: field.label,
      prompt: `Extract the ${field.label}.`,
    });
  }

  if (detection.detected_contacts.length > 0) {
    options.push({
      type: "contacts",
      key: "contacts:detected",
      label: `Contacts found in this document (${detection.detected_contacts.length})`,
      prompt:
        "Extract all contacts mentioned in the document, including names, roles, emails, and phone numbers.",
    });
  }

  return options;
}

export default function AnalysisRequest({
  disabled = false,
  waking = false,
  structureDetection = null,
  onAnalyze,
}: AnalysisRequestProps) {
  const detectedOptions = buildDetectedOptions(structureDetection);
  const hasDetections = detectedOptions.length > 0;
  const isKnownEmpty = Boolean(structureDetection) && !hasDetections;

  const detectedTypes = Array.from(
    new Set(detectedOptions.map((option) => option.type)),
  );

  const [initializedFor, setInitializedFor] =
    useState<StructureDetectionResult | null>(null);

  const [detectedType, setDetectedType] =
    useState<ExtractionType | null>(null);
  const [detectedTargetKey, setDetectedTargetKey] =
    useState<string | null>(null);

  const [templateType, setTemplateType] =
    useState<ExtractionType>("field");
  const [templateTargetId, setTemplateTargetId] = useState(
    EXTRACTION_TEMPLATES.field.targets[0].id,
  );

  const [instruction, setInstruction] = useState(
    EXTRACTION_TEMPLATES.field.targets[0].prompt,
  );
  const [badgeLabel, setBadgeLabel] = useState(
    EXTRACTION_TEMPLATES.field.label,
  );

  const [moreOptionsOpen, setMoreOptionsOpen] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");
  const [noMatch, setNoMatch] = useState(false);

  // Once detection results land (or come back empty), switch the
  // picker into the document-aware view instead of the generic
  // template it started on. Runs once per new detection result.
  if (structureDetection !== initializedFor) {
    setInitializedFor(structureDetection);
    setNoMatch(false);

    if (detectedTypes.length > 0) {
      const firstType = detectedTypes[0];
      const firstOption = detectedOptions.find(
        (option) => option.type === firstType,
      );

      if (firstOption) {
        setDetectedType(firstType);
        setDetectedTargetKey(firstOption.key);
        setInstruction(firstOption.prompt);
        setBadgeLabel(EXTRACTION_TEMPLATES[firstType].label);
      }
    } else if (Boolean(structureDetection)) {
      setTemplateType("custom");
      setTemplateTargetId(EXTRACTION_TEMPLATES.custom.targets[0].id);
      setInstruction(EXTRACTION_TEMPLATES.custom.targets[0].prompt);
      setBadgeLabel(EXTRACTION_TEMPLATES.custom.label);
    }
  }

  function applyDetected(option: DetectedOption) {
    setDetectedType(option.type);
    setDetectedTargetKey(option.key);
    setInstruction(option.prompt);
    setBadgeLabel(EXTRACTION_TEMPLATES[option.type].label);
    setNoMatch(false);
  }

  function handleDetectedTypeChange(nextType: ExtractionType) {
    const firstOption = detectedOptions.find(
      (option) => option.type === nextType,
    );

    if (firstOption) {
      applyDetected(firstOption);
    }
  }

  function handleDetectedTargetChange(nextKey: string) {
    const option = detectedOptions.find((item) => item.key === nextKey);

    if (option) {
      applyDetected(option);
    }
  }

  function applyTemplate(type: ExtractionType, template: ExtractionTemplate) {
    setTemplateType(type);
    setTemplateTargetId(template.id);
    setInstruction(template.prompt);
    setBadgeLabel(EXTRACTION_TEMPLATES[type].label);
    setNoMatch(false);
  }

  function handleTemplateTypeChange(nextType: ExtractionType) {
    applyTemplate(nextType, EXTRACTION_TEMPLATES[nextType].targets[0]);
  }

  function handleTemplateTargetChange(nextTargetId: string) {
    const template = EXTRACTION_TEMPLATES[templateType].targets.find(
      (item) => item.id === nextTargetId,
    );

    if (template) {
      applyTemplate(templateType, template);
    }
  }

  function switchToCustom() {
    setMoreOptionsOpen(true);
    applyTemplate("custom", EXTRACTION_TEMPLATES.custom.targets[0]);
    setInstruction("");
  }

  function chooseFirstDetected() {
    if (detectedOptions.length > 0) {
      applyDetected(detectedOptions[0]);
    }
  }

  async function continueAnalysis() {
    if (!instruction.trim()) {
      return;
    }

    setAnalyzing(true);
    setError("");
    setNoMatch(false);

    try {
      const result = await onAnalyze(instruction.trim());

      if (
        result.values.length === 0 &&
        result.tables.length === 0 &&
        !result.answer
      ) {
        setNoMatch(true);
      }
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

  const busy = disabled || analyzing;

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

      {hasDetections && (
        <>
          {structureDetection && (
            <p className="mt-4 text-xs text-slate-500">
              Detected as{" "}
              <span className="font-medium text-slate-700">
                {structureDetection.document_family_label}
              </span>
            </p>
          )}

          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <label className="block text-xs font-medium text-slate-500">
              Extraction Type
              <select
                value={detectedType ?? ""}
                disabled={busy}
                onChange={(event) =>
                  handleDetectedTypeChange(
                    event.target.value as ExtractionType,
                  )
                }
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
              >
                {detectedTypes.map((type) => (
                  <option key={type} value={type}>
                    {EXTRACTION_TEMPLATES[type].label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-xs font-medium text-slate-500">
              Extraction Target
              <select
                value={detectedTargetKey ?? ""}
                disabled={busy}
                onChange={(event) =>
                  handleDetectedTargetChange(event.target.value)
                }
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
              >
                {detectedOptions
                  .filter((option) => option.type === detectedType)
                  .map((option) => (
                    <option key={option.key} value={option.key}>
                      {option.label}
                    </option>
                  ))}
              </select>
            </label>
          </div>

          <div className="mt-4">
            <p className="text-xs font-medium text-slate-500">
              Detected in this document
            </p>

            <ul className="mt-2 space-y-1">
              {detectedOptions.map((option) => (
                <li key={option.key}>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => applyDetected(option)}
                    className="text-left text-sm text-slate-700 transition hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <span className="text-emerald-600">✓</span> {option.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </>
      )}

      {isKnownEmpty && structureDetection && (
        <div className="mt-4 rounded-xl bg-slate-50 p-4">
          <p className="text-xs font-medium text-slate-500">
            Document type
          </p>
          <p className="text-sm font-semibold text-slate-900">
            {structureDetection.document_family_label}
          </p>

          <p className="mt-3 text-xs font-medium text-slate-500">
            Detected content
          </p>
          <p className="mt-1 text-sm text-slate-700">
            {structureDetection.content_stats.tables} tables,{" "}
            {structureDetection.content_stats.dates} dates,{" "}
            {structureDetection.content_stats.currency_values} currency
            values, {structureDetection.content_stats.organizations}{" "}
            organizations
          </p>
        </div>
      )}

      {(!hasDetections || moreOptionsOpen) && (
        <div className={hasDetections ? "mt-5 border-t border-slate-100 pt-5" : "mt-5"}>
          {hasDetections && (
            <p className="mb-3 text-xs font-medium text-slate-500">
              More extraction options
            </p>
          )}

          <div className="flex flex-wrap gap-2">
            {EXTRACTION_TEMPLATES.custom.targets.map((template) => (
              <button
                key={template.id}
                type="button"
                disabled={busy}
                onClick={() => applyTemplate("custom", template)}
                className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-50"
              >
                {template.label}
              </button>
            ))}
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <label className="block text-xs font-medium text-slate-500">
              Extraction Type
              <select
                value={templateType}
                disabled={busy}
                onChange={(event) =>
                  handleTemplateTypeChange(
                    event.target.value as ExtractionType,
                  )
                }
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
              >
                {EXTRACTION_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {EXTRACTION_TEMPLATES[type].label}
                  </option>
                ))}
              </select>
            </label>

            <label className="block text-xs font-medium text-slate-500">
              Extraction Target
              <select
                value={templateTargetId}
                disabled={busy}
                onChange={(event) =>
                  handleTemplateTargetChange(event.target.value)
                }
                className="mt-1.5 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
              >
                {EXTRACTION_TEMPLATES[templateType].targets.map(
                  (target) => (
                    <option key={target.id} value={target.id}>
                      {target.label}
                    </option>
                  ),
                )}
              </select>
            </label>
          </div>
        </div>
      )}

      {hasDetections && !moreOptionsOpen && (
        <button
          type="button"
          onClick={() => setMoreOptionsOpen(true)}
          className="mt-4 flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-700"
        >
          <ChevronRight className="h-3.5 w-3.5" />
          More extraction options
        </button>
      )}

      {hasDetections && moreOptionsOpen && (
        <button
          type="button"
          onClick={() => setMoreOptionsOpen(false)}
          className="mt-3 flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-700"
        >
          <ChevronDown className="h-3.5 w-3.5" />
          Hide extraction options
        </button>
      )}

      <label className="mt-5 block text-xs font-medium text-slate-500">
        Instruction
        <textarea
          value={instruction}
          disabled={busy}
          onChange={(event) =>
            setInstruction(event.target.value)
          }
          rows={5}
          placeholder="Describe what to extract, or pick a target above to prefill this."
          className="mt-1.5 w-full resize-none rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
        />
      </label>

      <div className="mt-4 flex items-center gap-2">
        <span className="text-xs font-medium text-slate-500">
          Extraction Mode
        </span>
        <span className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
          {badgeLabel}
        </span>
      </div>

      <button
        type="button"
        disabled={busy || !instruction.trim()}
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

      {noMatch && (
        <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-semibold text-amber-800">
            No matching structure found
          </p>
          <p className="mt-1 text-sm text-amber-700">
            That request didn&apos;t match anything in this document.
          </p>

          {structureDetection && structureDetection.detected_tables.length > 0 && (
            <>
              <p className="mt-3 text-xs font-medium text-amber-700">
                Detected tables
              </p>
              <ul className="mt-1 space-y-0.5 text-sm text-amber-800">
                {structureDetection.detected_tables.map((table) => (
                  <li key={table.key}>&bull; {table.label}</li>
                ))}
              </ul>
            </>
          )}

          <div className="mt-3 flex flex-wrap gap-2">
            {hasDetections && (
              <button
                type="button"
                onClick={chooseFirstDetected}
                className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-800 transition hover:bg-amber-100"
              >
                Choose Detected Table
              </button>
            )}
            <button
              type="button"
              onClick={switchToCustom}
              className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-xs font-medium text-amber-800 transition hover:bg-amber-100"
            >
              Try Custom Extraction
            </button>
          </div>
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
