export default function GlobalLoading() {
  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 px-6">
      <div className="h-8 w-8 animate-pulse rounded-full border-2 border-border border-t-primary" />
      <p className="text-sm text-text-secondary">Loading workspace…</p>
    </div>
  );
}
