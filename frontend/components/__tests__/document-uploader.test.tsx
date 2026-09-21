import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import DocumentUploader from "@/components/document-uploader";

const {
  startBackendWarmupMock,
  ensureBackendHealthyMock,
  getWarmupStatusMock,
  subscribeWarmupStatusMock,
} = vi.hoisted(() => ({
  startBackendWarmupMock: vi.fn(),
  ensureBackendHealthyMock: vi.fn(),
  getWarmupStatusMock: vi.fn(),
  subscribeWarmupStatusMock: vi.fn(),
}));

vi.mock("@/lib/backend-warmup", () => ({
  startBackendWarmup: startBackendWarmupMock,
  ensureBackendHealthy: ensureBackendHealthyMock,
  getWarmupStatus: getWarmupStatusMock,
  subscribeWarmupStatus: subscribeWarmupStatusMock,
  markUploadStarted: vi.fn(),
  markUploadCompleted: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  wakeBackend: vi.fn(),
}));

const { uploadFileWithProgressMock } = vi.hoisted(() => ({
  uploadFileWithProgressMock: vi.fn(),
}));

vi.mock("@/lib/upload", () => ({
  uploadFileWithProgress: uploadFileWithProgressMock,
}));

vi.mock("@/lib/documents", () => ({
  resolveDuplicate: vi.fn(),
  selectPortfolioFile: vi.fn(),
}));

async function selectFile(name = "contract.pdf") {
  const file = new File(["%PDF-1.4"], name, { type: "application/pdf" });
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  await act(async () => {
    fireEvent.change(input, { target: { files: [file] } });
  });
  await waitFor(() => expect(screen.getByText(name)).toBeInTheDocument());
  return file;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("DocumentUploader", () => {
  let statusListener: ((status: string) => void) | null = null;

  beforeEach(() => {
    statusListener = null;
    startBackendWarmupMock.mockReset();
    ensureBackendHealthyMock.mockReset();
    getWarmupStatusMock.mockReset();
    subscribeWarmupStatusMock.mockReset();
    uploadFileWithProgressMock.mockReset();

    startBackendWarmupMock.mockResolvedValue(undefined);
    ensureBackendHealthyMock.mockResolvedValue(undefined);
    getWarmupStatusMock.mockReturnValue("healthy");
    subscribeWarmupStatusMock.mockImplementation((listener: (s: string) => void) => {
      statusListener = listener;
      listener(getWarmupStatusMock());
      return () => {
        statusListener = null;
      };
    });
  });

  it("starts background warm-up on mount and uploads immediately when already healthy", async () => {
    const uploadResult = deferred<unknown>();
    uploadFileWithProgressMock.mockReturnValue(uploadResult.promise);
    const onUploadComplete = vi.fn();

    render(<DocumentUploader onUploadComplete={onUploadComplete} />);

    await waitFor(() => expect(startBackendWarmupMock).toHaveBeenCalledTimes(1));

    await selectFile();
    fireEvent.click(screen.getByRole("button", { name: /upload document/i }));

    await waitFor(() =>
      expect(screen.getByText(/uploading document/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/connecting to processing service/i)).not.toBeInTheDocument();
    expect(ensureBackendHealthyMock).not.toHaveBeenCalled();

    act(() => {
      uploadResult.resolve({
        document_id: "doc-1",
        original_filename: "contract.pdf",
        status: "completed",
      });
    });

    await waitFor(() => expect(onUploadComplete).toHaveBeenCalledTimes(1));
  });

  it("keeps the selected file while connecting, then auto-uploads when healthy", async () => {
    getWarmupStatusMock.mockReturnValue("warming");
    const ready = deferred<void>();
    ensureBackendHealthyMock.mockReturnValue(ready.promise);
    startBackendWarmupMock.mockReturnValue(ready.promise);

    const uploadResult = deferred<unknown>();
    uploadFileWithProgressMock.mockReturnValue(uploadResult.promise);
    const onUploadComplete = vi.fn();

    render(<DocumentUploader onUploadComplete={onUploadComplete} />);

    const file = await selectFile("cold-start.pdf");
    expect(screen.getByText(/file ready/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /upload document/i }));

    await waitFor(() =>
      expect(
        screen.getByText(/connecting to processing service/i),
      ).toBeInTheDocument(),
    );
    expect(
      screen.getByText(/your file is ready and will upload automatically/i),
    ).toBeInTheDocument();
    expect(screen.getByText("cold-start.pdf")).toBeInTheDocument();
    expect(uploadFileWithProgressMock).not.toHaveBeenCalled();

    getWarmupStatusMock.mockReturnValue("healthy");
    act(() => {
      statusListener?.("healthy");
      ready.resolve();
    });

    await waitFor(() => expect(uploadFileWithProgressMock).toHaveBeenCalledTimes(1));
    expect(uploadFileWithProgressMock.mock.calls[0][1]).toBe(file);

    act(() => {
      uploadResult.resolve({
        document_id: "doc-2",
        original_filename: "cold-start.pdf",
        status: "completed",
      });
    });

    await waitFor(() => expect(onUploadComplete).toHaveBeenCalledTimes(1));
  });

  it("surfaces a failed upload and lets the user retry from the same selected file", async () => {
    uploadFileWithProgressMock.mockRejectedValueOnce(new Error("Server exploded."));
    const onUploadComplete = vi.fn();

    render(<DocumentUploader onUploadComplete={onUploadComplete} />);
    await waitFor(() => expect(startBackendWarmupMock).toHaveBeenCalledTimes(1));

    await selectFile();
    fireEvent.click(screen.getByRole("button", { name: /upload document/i }));

    await waitFor(() => expect(screen.getByText("Server exploded.")).toBeInTheDocument());
    expect(onUploadComplete).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: /upload document/i }),
    ).not.toBeDisabled();
  });
});
