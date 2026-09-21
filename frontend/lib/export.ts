export function downloadBlob(
  content: string | Blob,
  filename: string,
  type: string,
) {
  const blob =
    content instanceof Blob ? content : new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: unknown): string {
  return `"${String(value ?? "").replaceAll('"', '""')}"`;
}

export function toCsv(headers: string[], rows: Record<string, unknown>[]): string {
  const lines = [
    headers.map(csvCell).join(","),
    ...rows.map((row) => headers.map((header) => csvCell(row[header])).join(",")),
  ];
  return lines.join("\n");
}

export function toTsv(headers: string[], rows: Record<string, unknown>[]): string {
  const lines = [
    headers.join("\t"),
    ...rows.map((row) =>
      headers.map((header) => String(row[header] ?? "")).join("\t"),
    ),
  ];
  return lines.join("\n");
}

export function downloadCsv(
  filename: string,
  headers: string[],
  rows: Record<string, unknown>[],
) {
  downloadBlob(toCsv(headers, rows), filename, "text/csv;charset=utf-8;");
}

export function downloadJson(filename: string, data: unknown) {
  downloadBlob(
    JSON.stringify(data, null, 2),
    filename,
    "application/json;charset=utf-8;",
  );
}
