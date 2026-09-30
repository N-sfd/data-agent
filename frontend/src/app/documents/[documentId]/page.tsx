"use client";

import { Suspense } from "react";
import { useParams } from "next/navigation";

import DocumentWorkspace from "@/components/documents/document-workspace";

export default function DocumentWorkspacePage() {
  return (
    <Suspense fallback={null}>
      <DocumentWorkspaceRoute />
    </Suspense>
  );
}

function DocumentWorkspaceRoute() {
  const params = useParams<{ documentId: string }>();
  return <DocumentWorkspace documentId={params.documentId} />;
}
