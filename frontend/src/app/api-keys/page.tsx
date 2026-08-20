import PageHeader from "@/components/page-header";

export default function ApiKeysPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <PageHeader
        title="API Keys"
        description="Manage integration keys for external systems."
      />
      <div className="rounded-xl border border-border bg-surface p-8 text-center">
        <p className="text-sm font-medium text-foreground">Coming Soon</p>
        <p className="mt-1 text-sm text-text-secondary">
          API key management will be available in a future release.
        </p>
      </div>
    </div>
  );
}
