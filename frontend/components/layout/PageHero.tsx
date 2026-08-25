import type { ReactNode } from "react";

interface PageHeroProps {
  eyebrow?: string;
  title: ReactNode;
  description?: string;
  actions?: ReactNode;
  visual?: ReactNode;
}

export default function PageHero({
  eyebrow,
  title,
  description,
  actions,
  visual,
}: PageHeroProps) {
  return (
    <section className="page-hero">
      <div
        className={[
          "page-hero-inner",
          visual ? "page-hero-split" : "",
        ].join(" ")}
      >
        <div className="page-hero-copy">
          {eyebrow && <p className="page-hero-eyebrow">{eyebrow}</p>}
          <h1 className="page-hero-title">{title}</h1>
          {description && (
            <p className="page-hero-description">{description}</p>
          )}
          {actions && <div className="page-hero-actions">{actions}</div>}
        </div>
        {visual && <div className="page-hero-visual">{visual}</div>}
      </div>
    </section>
  );
}
