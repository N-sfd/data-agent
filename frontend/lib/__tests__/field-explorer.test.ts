import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/documents", () => ({
  getContractAnalysis: vi.fn(),
  getExtractResults: vi.fn(),
  searchDocuments: vi.fn(),
}));

import { searchDocuments, getContractAnalysis } from "@/lib/documents";
import { aggregateFieldAcrossRepository } from "@/lib/field-explorer";

describe("aggregateFieldAcrossRepository concurrency", () => {
  it("never has more than 5 document loads in flight at once", async () => {
    const documents = Array.from({ length: 23 }, (_, i) => ({
      document_id: `doc-${i}`,
      original_filename: `doc-${i}.pdf`,
      counterparty: null,
      effective_date: null,
      expiration_date: null,
    }));

    vi.mocked(searchDocuments).mockResolvedValue({
      documents: documents as never,
      total: documents.length,
    } as never);

    let inFlight = 0;
    let maxInFlight = 0;

    vi.mocked(getContractAnalysis).mockImplementation(async () => {
      inFlight += 1;
      maxInFlight = Math.max(maxInFlight, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 5));
      inFlight -= 1;
      return { metadata_fields: [] } as never;
    });

    await aggregateFieldAcrossRepository("payment_terms" as never);

    expect(getContractAnalysis).toHaveBeenCalledTimes(documents.length);
    expect(maxInFlight).toBeLessThanOrEqual(5);
    expect(maxInFlight).toBeGreaterThan(1); // actually parallel, not serial
  });
});
