import type { ReactNode } from "react";

interface PageHeroProps {
  eyebrow?: string;
  title: ReactNode;
  description?: string;
  actions?: ReactNode;
}

export default function PageHero({
  eyebrow,
  title,
  description,
  actions,
}: PageHeroProps) {
  return (
    <section className="page-hero">
      <div className="page-hero-inner">
        {eyebrow && <p className="page-hero-eyebrow">{eyebrow}</p>}
        <h1 className="page-hero-title">{title}</h1>
        {description && (
          <p className="page-hero-description">{description}</p>
        )}
        {actions && <div className="page-hero-actions">{actions}</div>}
      </div>
    </section>
  );
}
