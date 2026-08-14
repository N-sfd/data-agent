"use client";

import {
  FileText,
  Table2,
} from "lucide-react";

import type {
  FinancialAnalysisResult,
} from "@/types/document";


interface FinancialTablesProps {
  result: FinancialAnalysisResult;
}


export default function FinancialTables({
  result,
}: FinancialTablesProps) {

  return (
    <div className="space-y-6">

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">

        <div className="flex items-start gap-3">

          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
            <Table2 className="h-5 w-5 text-blue-600" />
          </div>

          <div>

            <h2 className="text-lg font-semibold text-slate-950">
              Financial extraction
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              {result.instruction}
            </p>

          </div>

        </div>

        <div className="mt-5 flex flex-wrap gap-2">

          {result.pages_used.map(
            (pageNumber) => (
              <span
                key={pageNumber}
                className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600"
              >
                Page {pageNumber}
              </span>
            )
          )}

        </div>

      </div>


      {result.warnings.map(
        (warning) => (
          <div
            key={warning}
            className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"
          >
            {warning}
          </div>
        )
      )}


      {result.tables.length === 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center shadow-sm">

          <Table2 className="mx-auto h-9 w-9 text-slate-300" />

          <p className="mt-3 font-medium text-slate-700">
            No structured table detected
          </p>

          <p className="mt-1 text-sm text-slate-500">
            Try specifying a page range or a different financial section.
          </p>

        </div>
      )}


      {result.tables.map(
        (table) => (

          <div
            key={table.table_id}
            className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
          >

            <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">

              <div>

                <p className="font-semibold text-slate-900">
                  Extracted table
                </p>

                <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">

                  <FileText className="h-3.5 w-3.5" />

                  {table.source_reference}

                </div>

              </div>


              <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">

                {Math.round(
                  table.confidence * 100
                )}
                % confidence

              </span>

            </div>


            <div className="overflow-x-auto">

              <table className="min-w-full text-sm">

                <thead className="bg-slate-50">

                  <tr>

                    {table.headers.map(
                      (header) => (
                        <th
                          key={header}
                          className="whitespace-nowrap border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700"
                        >
                          {header}
                        </th>
                      )
                    )}

                  </tr>

                </thead>


                <tbody>

                  {table.rows.map(
                    (row, rowIndex) => (

                      <tr
                        key={rowIndex}
                        className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                      >

                        {table.headers.map(
                          (header) => (

                            <td
                              key={header}
                              className="whitespace-nowrap px-4 py-3 text-slate-700"
                            >
                              {String(
                                row[header] ?? ""
                              )}
                            </td>

                          )
                        )}

                      </tr>

                    )
                  )}

                </tbody>

              </table>

            </div>

          </div>
        )
      )}

    </div>
  );
}
