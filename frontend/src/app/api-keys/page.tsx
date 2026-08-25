import ContentSection from "@/components/layout/ContentSection";
import PageHero from "@/components/layout/PageHero";

export default function ApiKeysPage() {
  return (
    <>
      <PageHero
        eyebrow="Governance"
        title="API Keys"
        description="Manage integration keys for external systems and automation."
      />

      <ContentSection>
        <div className="editorial-card p-10 text-center">
          <p className="text-base font-medium text-foreground">Coming soon</p>
          <p className="mt-2 text-sm text-text-secondary">
            API key management will be available in a future release.
          </p>
        </div>
      </ContentSection>
    </>
  );
}
