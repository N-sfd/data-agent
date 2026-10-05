/** Human names for how a value was found. Internal method ids
 * ("inline_regex", "field_probe") stay in processing details; the UI says
 * what kind of detection it was. */
const RULES: [RegExp, string][] = [
  [/xml/i, "XML Element"],
  [/ocr|tesseract/i, "OCR"],
  [/table|grid|schedule/i, "Table Detection"],
  [/regex|pattern|inline/i, "Pattern Match"],
  [/form|cell_geometry|acroform/i, "Form Detection"],
  [/dom|html/i, "HTML Structure"],
  [/probe|label|kv|key_value|field/i, "Field Detection"],
  [/\bai\b|llm|gemini|model/i, "AI Assist"],
  [/layout|native|text/i, "Text Layout"],
];

export function humanizeMethod(method: string | null | undefined): string {
  const raw = (method ?? "").split("+")[0].trim();
  if (!raw) return "";
  for (const [pattern, label] of RULES) {
    if (pattern.test(raw)) return label;
  }
  return raw
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1).toLowerCase())
    .join(" ");
}

/** "'Action: Sync' on page 1 (inline_regex)" -> "… (Pattern Match)". */
export function humanizeExample(example: string): string {
  return example.replace(/\(([a-z][a-z0-9_+]*)\)\s*$/i, (whole: string, method: string) =>
    // Only method ids ("inline_regex", "ocr"), never a value such as "(USD)".
    method.includes("_") || RULES.some(([pattern]) => pattern.test(method)) ? `(${humanizeMethod(method)})` : whole,
  );
}
