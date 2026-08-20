import Link from "next/link";

import PageHeader from "@/components/page-header";

export default function ComingSoonPage({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mx-auto max-w-3xl px-6 py-8">
      <PageHeader title={title} description={description} />
      <div className="rounded-xl border border-border bg-surface p-8 text-center">
        <p className="text-sm font-medium text-foreground">Coming Soon</p>
        <p className="mt-2 text-sm text-text-secondary">
          This module is planned for a future release. Explore{" "}
          <Link href="/repository" className="text-brand-blue hover:underline">
            Repository
          </Link>{" "}
          or{" "}
          <Link href="/explorer" className="text-brand-blue hover:underline">
            Field Explorer
          </Link>{" "}
          in the meantime.
        </p>
      </div>
    </div>
  );
}
