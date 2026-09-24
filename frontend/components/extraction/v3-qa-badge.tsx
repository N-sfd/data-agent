"use client";

export function isNeedsReview(value: unknown): boolean {
  const text = value == null ? "" : String(value).toLowerCase();
  return text.includes("review");
}

export function isVerifiedOrPass(value: unknown): boolean {
  const text = value == null ? "" : String(value).toLowerCase();
  return text.includes("verified") || text.includes("pass");
}

export default function QaBadge({ value }: { value: unknown }) {
  const text = value == null ? "" : String(value);
  if (!text) return null;
  const tone = isVerifiedOrPass(text)
    ? "bg-success/15 text-success"
    : isNeedsReview(text)
      ? "bg-warning/15 text-warning"
      : "bg-surface-soft text-text-secondary";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${tone}`}>
      {text}
    </span>
  );
}
