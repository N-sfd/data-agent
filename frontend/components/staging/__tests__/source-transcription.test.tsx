import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SourceTranscription from "@/components/staging/source-transcription";
import type { DocumentPage, PageTranscript } from "@/types/document";

const { pagesMock, transcriptMock, panelProps } = vi.hoisted(() => ({
  pagesMock: vi.fn(),
  transcriptMock: vi.fn(),
  panelProps: [] as unknown[],
}));

vi.mock("@/lib/documents", () => ({
  getDocumentPages: pagesMock,
  getPageTranscript: transcriptMock,
}));

vi.mock("@/components/source-verification-panel", () => ({
  default: (props: unknown) => {
    panelProps.push(props);
    return <div data-testid="source-panel" />;
  },
}));

const PAGE = {
  document_id: "doc-1",
  page_number: 1,
  page_label: null,
  extraction_method: "ocr",
  word_count: 176,
  final_text: "So7  aSBaise}Ze       ON ond\nCertificate No,   _422005/155187",
} as unknown as DocumentPage;

const TRANSCRIPT: PageTranscript = {
  document_id: "doc-1",
  page_number: 1,
  source_type: "image",
  extraction_method: "ocr",
  word_count: 176,
  page_width: 612,
  page_height: 792,
  warnings: [],
  blocks: [
    { kind: "heading", text: "EXAMINATION BOARD", bbox: [50, 30, 400, 45], table: null,
      lines: [{ text: "EXAMINATION BOARD", bbox: [50, 30, 400, 45], words: [] }] },
    { kind: "paragraph", text: "Roll No.   516522", bbox: [58, 110, 200, 122], table: null,
      lines: [{ text: "Roll No.   516522", bbox: [58, 110, 200, 122], words: [] }] },
    { kind: "table", text: "", bbox: [100, 480, 460, 560], table: { headers: [], rows: [["1.", "ENGLISH", "200", "069"]] },
      lines: [{ text: "1. | ENGLISH | 200 | 069", bbox: [100, 480, 460, 495], words: [] }] },
  ],
};

describe("SourceTranscription (Source & Transcript)", () => {
  beforeEach(() => {
    pagesMock.mockResolvedValue([PAGE]);
    transcriptMock.mockResolvedValue(TRANSCRIPT);
    panelProps.length = 0;
  });

  it("shows the reconstructed transcript beside the source, raw OCR only as a diagnostic", async () => {
    render(<SourceTranscription documentId="doc-1" documentName="FA.jpg" />);
    expect(await screen.findByText("EXAMINATION BOARD")).toBeInTheDocument();
    expect(screen.getByTestId("source-panel")).toBeInTheDocument();
    expect(screen.getByText("Roll No.")).toBeInTheDocument();
    expect(screen.getByText("516522")).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("ENGLISH");
    expect(screen.getByText(/OCR · 176/)).toBeInTheDocument();

    // Raw engine text lives inside the collapsed diagnostics disclosure.
    const raw = screen.getByText(/So7 aSBaise/);
    expect(raw.closest("details")).not.toBeNull();
    expect(screen.getByText("Raw OCR diagnostics")).toBeInTheDocument();
  });

  it("highlights a clicked transcript line's region in the source", async () => {
    render(<SourceTranscription documentId="doc-1" documentName="FA.jpg" />);
    fireEvent.click((await screen.findByText("516522")).closest("button")!);
    const last = panelProps.at(-1) as { request: { pageNumber: number; region: number[] } };
    expect(last.request.pageNumber).toBe(1);
    expect(last.request.region).toEqual([58, 110, 200, 122]);
  });
});

describe("SourceTranscription text-only pages", () => {
  beforeEach(() => {
    pagesMock.mockResolvedValue([PAGE]);
    panelProps.length = 0;
  });

  it("labels a page without source positions as text-only and never offers highlighting", async () => {
    transcriptMock.mockResolvedValue({
      ...TRANSCRIPT,
      positioning: "text_only",
      blocks: [
        { kind: "paragraph", text: "Certificate No.   422005/155187", bbox: null, table: null,
          lines: [{ text: "Certificate No.   422005/155187", bbox: null, words: [] }] },
      ],
    });
    render(<SourceTranscription documentId="doc-1" documentName="FA.jpg" />);
    expect(await screen.findByText("Text-only transcription")).toBeInTheDocument();
    expect(screen.getByText(/Source positioning was not available for this page/)).toBeInTheDocument();
    const line = screen.getByText("422005/155187").closest("button")!;
    expect(line).toBeDisabled();
    fireEvent.click(line);
    const last = panelProps.at(-1) as { request: { region?: unknown } };
    expect(last.request.region ?? null).toBeNull();
  });
});
