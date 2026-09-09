import type { ReactNode } from "react";

interface PageHeroProps {
  eyebrow?: string;
  title: ReactNode;
  description?: string;
  actions?: ReactNode;
  visual?: ReactNode;
  /** Small secondary line under the description (e.g. specialization link). */
  specialization?: ReactNode;
}

export default function PageHero({
  eyebrow,
  title,
  description,
  actions,
  visual,
  specialization,
}: PageHeroProps) {
  return (
    <section className="page-hero">
      <div
        className={[
          "page-hero-inner",
          visual ? "page-hero-split" : "",
        ].join(" ")}
      >
        <div className="page-hero-copy min-w-0 w-full">
          {eyebrow && <p className="page-hero-eyebrow">{eyebrow}</p>}
          <h1 className="page-hero-title">{title}</h1>
          {description && (
            <div className="page-hero-description-wrap max-w-2xl">
              <p className="page-hero-description">{description}</p>
            </div>
          )}
          {specialization && <div className="mt-3">{specialization}</div>}
          {actions && <div className="page-hero-actions">{actions}</div>}
        </div>
        {visual && <div className="page-hero-visual">{visual}</div>}
      </div>
    </section>
  );
}
