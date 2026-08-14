"use client";

import { ArrowRight, Search } from "lucide-react";
import { useState } from "react";

interface AnalysisRequestProps {
  disabled?: boolean;

  onAnalyze: (
    instruction: string
  ) => Promise<void>;
}

const quickPrompts = [
  "Extract contract number and award date",
  "Find every email and telephone number",
  "Extract all CLINs with prices",
  "Find NAICS codes and size standards",
  "What is the minimum contract guarantee?",
  "Summarize cybersecurity requirements",
];

export default function AnalysisRequest({
  disabled = false,
  onAnalyze,
}: AnalysisRequestProps) {
  const [instruction, setInstruction] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState("");

  function choosePrompt(prompt: string) {
    setInstruction(prompt);
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

      <textarea
        value={instruction}
        disabled={disabled || analyzing}
        onChange={(event) =>
          setInstruction(event.target.value)
        }
        rows={5}
        placeholder={`Examples:
• Extract contract number and award date
• Find every email and telephone number
• Extract all CLINs with prices
• Find NAICS codes and size standards
• What is the minimum contract guarantee?
• Summarize cybersecurity requirements
• Extract tables from pages 15–25`}
        className="mt-5 w-full resize-none rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-50 disabled:bg-slate-50"
      />

      <div className="mt-4 flex flex-wrap gap-2">
        {quickPrompts.map((prompt) => (
          <button
            key={prompt}
            type="button"
            disabled={disabled || analyzing}
            onClick={() => choosePrompt(prompt)}
            className="rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 disabled:opacity-50"
          >
            {prompt}
          </button>
        ))}
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

      {error && (
        <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error}
        </div>
      )}
    </div>
  );
}
