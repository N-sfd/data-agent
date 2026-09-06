import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";

import DocumentUploader from "@/components/document-uploader";

const { wakeBackendMock } = vi.hoisted(() => ({
  wakeBackendMock: vi.fn(),
}));

vi.mock("@/lib/api", () => ({
  wakeBackend: wakeBackendMock,
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
  beforeEach(() => {
    wakeBackendMock.mockReset();
    uploadFileWithProgressMock.mockReset();
  });

  it("uploads immediately, without a service_starting stage, once pre-warm has already resolved", async () => {
    wakeBackendMock.mockResolvedValue(undefined);
    const uploadResult = deferred<unknown>();
    uploadFileWithProgressMock.mockReturnValue(uploadResult.promise);
    const onUploadComplete = vi.fn();

    render(<DocumentUploader onUploadComplete={onUploadComplete} />);

    // Let the mount-time pre-warm resolve before the user does anything.
    await waitFor(() => expect(wakeBackendMock).toHaveBeenCalledTimes(1));

    await selectFile();
    fireEvent.click(screen.getByRole("button", { name: /upload document/i }));

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /uploading/i })).toBeInTheDocument(),
    );
    expect(screen.queryByText(/preparing/i)).not.toBeInTheDocument();
    // Only the one mount-time pre-warm call — clicking Upload after it
    // already resolved must not trigger a second /health hit.
    expect(wakeBackendMock).toHaveBeenCalledTimes(1);

    act(() => {
      uploadResult.resolve({
        document_id: "doc-1",
        original_filename: "contract.pdf",
        status: "completed",
      });
    });

    await waitFor(() => expect(onUploadComplete).toHaveBeenCalledTimes(1));
  });

  it("shows service_starting (no fake percentage) while cold, then auto-uploads the already-selected file once ready", async () => {
    const prewarm = deferred<void>();
    wakeBackendMock.mockReturnValueOnce(prewarm.promise);
    const uploadResult = deferred<unknown>();
    uploadFileWithProgressMock.mockReturnValue(uploadResult.promise);
    const onUploadComplete = vi.fn();

    render(<DocumentUploader onUploadComplete={onUploadComplete} />);

    const file = await selectFile("cold-start.pdf");
    fireEvent.click(screen.getByRole("button", { name: /upload document/i }));

    // Still cold: the uploader must say the service is starting, not
    // show any percentage, and must not have asked the user to reselect.
    await waitFor(() =>
      expect(screen.getByText(/preparing processing service/i)).toBeInTheDocument(),
    );
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.getByText("cold-start.pdf")).toBeInTheDocument();
    expect(uploadFileWithProgressMock).not.toHaveBeenCalled();

    // Backend finishes waking — upload should fire automatically with
    // the same File, no re-selection required.
    act(() => prewarm.resolve());

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
    wakeBackendMock.mockResolvedValue(undefined);
    uploadFileWithProgressMock.mockRejectedValueOnce(new Error("Server exploded."));
    const onUploadComplete = vi.fn();

    render(<DocumentUploader onUploadComplete={onUploadComplete} />);
    await waitFor(() => expect(wakeBackendMock).toHaveBeenCalledTimes(1));

    await selectFile();
    fireEvent.click(screen.getByRole("button", { name: /upload document/i }));

    await waitFor(() => expect(screen.getByText("Server exploded.")).toBeInTheDocument());
    expect(onUploadComplete).not.toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: /upload document/i }),
    ).not.toBeDisabled();
  });
});
