interface WorkflowBreadcrumbProps {
  activeStep: "upload" | "extract" | "review" | "repository";
}

const STEPS = [
  { id: "upload" as const, label: "Upload" },
  { id: "extract" as const, label: "Extract" },
  { id: "review" as const, label: "Review" },
  { id: "repository" as const, label: "Repository" },
];

export default function WorkflowBreadcrumb({
  activeStep,
}: WorkflowBreadcrumbProps) {
  const activeIndex = STEPS.findIndex((s) => s.id === activeStep);

  return (
    <nav aria-label="Extraction workflow" className="workflow-steps">
      {STEPS.map((step, index) => (
        <span key={step.id} className="inline-flex items-center gap-3">
          {index > 0 && <span className="workflow-separator">/</span>}
          <span
            className={
              index < activeIndex
                ? "step-done"
                : index === activeIndex
                  ? "step-active"
                  : ""
            }
          >
            {step.label}
          </span>
        </span>
      ))}
    </nav>
  );
}
