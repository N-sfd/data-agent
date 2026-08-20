import type { ReactNode } from "react";

interface ContentSectionProps {
  children: ReactNode;
  className?: string;
  wide?: boolean;
}

export default function ContentSection({
  children,
  className = "",
  wide = false,
}: ContentSectionProps) {
  return (
    <section
      className={[
        wide ? "content-section-wide" : "content-section",
        className,
      ].join(" ")}
    >
      {children}
    </section>
  );
}
