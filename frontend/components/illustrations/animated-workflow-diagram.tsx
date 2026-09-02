"use client";

import { useEffect, useState } from "react";

import WorkflowDiagram from "@/components/illustrations/workflow-diagram";

const STEP_IDS = [
  "upload",
  "understand",
  "extract",
  "verify",
  "repository",
] as const;

type StepId = (typeof STEP_IDS)[number];

const CYCLE_MS = 2200;

interface AnimatedWorkflowDiagramProps {
  compact?: boolean;
  className?: string;
}

export default function AnimatedWorkflowDiagram({
  compact,
  className,
}: AnimatedWorkflowDiagramProps) {
  const [activeStep, setActiveStep] = useState<StepId | undefined>(
    undefined,
  );

  useEffect(() => {
    const reduceMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    if (reduceMotion) return;

    let index = 0;
    setActiveStep(STEP_IDS[0]);

    const interval = window.setInterval(() => {
      index = (index + 1) % STEP_IDS.length;
      setActiveStep(STEP_IDS[index]);
    }, CYCLE_MS);

    return () => window.clearInterval(interval);
  }, []);

  return (
    <WorkflowDiagram
      activeStep={activeStep}
      compact={compact}
      className={className}
    />
  );
}
