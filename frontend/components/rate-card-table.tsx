import { Table2 } from "lucide-react";

import type { NormalizedTable } from "@/types/document";

interface RateCardTableProps {
  tables: NormalizedTable[];
}

export default function RateCardTable({
  tables,
}: RateCardTableProps) {
  if (tables.length === 0) {
    return null;
  }

  return (
    <div className="space-y-4">
      {tables.map((table) => (
        <div
          key={table.table_id}
          className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
        >
          <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
            <div className="flex items-center gap-2">
              <Table2 className="h-4 w-4 text-blue-600" />
              <p className="text-sm font-semibold text-slate-900">
                {table.table_type === "rate_card"
                  ? "Rate Card"
                  : "Table"}
              </p>
            </div>

            <p className="text-xs text-slate-500">
              {table.source_reference}
            </p>
          </div>

          <div className="overflow-x-auto">
            {table.table_type === "rate_card" ? (
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700">
                      Role
                    </th>
                    <th className="border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700">
                      Rate
                    </th>
                    <th className="border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700">
                      Unit
                    </th>
                    <th className="border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700">
                      Currency
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {table.rate_card_rows.map((row, index) => (
                    <tr
                      key={index}
                      className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                    >
                      <td className="px-4 py-3 text-slate-700">
                        {row.role}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {row.rate ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {row.unit ?? "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-700">
                        {row.currency ?? "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    {table.headers.map((header) => (
                      <th
                        key={header}
                        className="whitespace-nowrap border-b border-slate-200 px-4 py-3 text-left font-semibold text-slate-700"
                      >
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {table.rows.map((row, rowIndex) => (
                    <tr
                      key={rowIndex}
                      className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                    >
                      {table.headers.map((header) => (
                        <td
                          key={header}
                          className="whitespace-nowrap px-4 py-3 text-slate-700"
                        >
                          {String(row[header] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
