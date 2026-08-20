import type { ReactNode } from "react";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  size?: "default" | "hero";
  eyebrow?: string;
}

export default function PageHeader({
  title,
  description,
  actions,
  size = "default",
  eyebrow,
}: PageHeaderProps) {
  return (
    <div className="mb-12 flex flex-wrap items-start justify-between gap-6">
      <div className="max-w-3xl">
        {eyebrow && <p className="eyebrow">{eyebrow}</p>}
        <h1
          className={[
            eyebrow ? "mt-3" : "",
            size === "hero" ? "headline-editorial" : "headline-editorial text-[clamp(2rem,3.5vw,2.625rem)]",
          ].join(" ")}
        >
          {title}
        </h1>
        {description && (
          <p className="mt-4 max-w-2xl text-[15px] leading-7 text-text-secondary sm:text-base">
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-3">{actions}</div>
      )}
    </div>
  );
}
