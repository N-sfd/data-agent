"use client";

import { Suspense } from "react";

import DocumentsHome from "@/components/documents/documents-home";

export default function DocumentsPage() {
  return (
    <Suspense>
      <DocumentsHome />
    </Suspense>
  );
}
