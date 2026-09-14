import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { getCurrentActorMock } = vi.hoisted(() => ({
  getCurrentActorMock: vi.fn(),
}));

vi.mock("@/lib/auth", () => ({
  getCurrentActor: getCurrentActorMock,
}));

import { ApiError } from "@/lib/api";
import AdminSessionKey from "@/components/admin-session-key";

const ACTOR = {
  id: "actor-1",
  actor_type: "user",
  display_name: "Jane Admin",
  email: null,
  role: "admin",
  active: true,
  permissions: ["documents.delete"],
};

describe("AdminSessionKey", () => {
  beforeEach(() => {
    getCurrentActorMock.mockReset();
    window.localStorage.clear();
  });

  afterEach(() => {
    window.localStorage.clear();
  });

  it("shows the key input when nothing is stored", async () => {
    render(<AdminSessionKey />);

    await waitFor(() =>
      expect(screen.getByPlaceholderText("Service API key")).toBeInTheDocument(),
    );
  });

  it("saves and shows the resolved actor after a valid key", async () => {
    getCurrentActorMock.mockResolvedValue(ACTOR);

    render(<AdminSessionKey />);
    await waitFor(() => screen.getByPlaceholderText("Service API key"));

    fireEvent.change(screen.getByPlaceholderText("Service API key"), {
      target: { value: "good-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(screen.getByText("Signed in as Jane Admin")).toBeInTheDocument();
    });

    expect(getCurrentActorMock).toHaveBeenCalledWith("good-key");
    expect(window.localStorage.getItem("data-agent-access-token")).toBe(
      "good-key",
    );
  });

  it("shows an error and does not persist an invalid key", async () => {
    getCurrentActorMock.mockRejectedValue(new ApiError("nope", 401));

    render(<AdminSessionKey />);
    await waitFor(() => screen.getByPlaceholderText("Service API key"));

    fireEvent.change(screen.getByPlaceholderText("Service API key"), {
      target: { value: "bad-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(screen.getByText(/wasn't recognized/i)).toBeInTheDocument();
    });

    expect(window.localStorage.getItem("data-agent-access-token")).toBeNull();
  });

  it("restores a signed-in state from a previously stored key", async () => {
    window.localStorage.setItem("data-agent-access-token", "existing-key");
    getCurrentActorMock.mockResolvedValue(ACTOR);

    render(<AdminSessionKey />);

    await waitFor(() => {
      expect(screen.getByText("Signed in as Jane Admin")).toBeInTheDocument();
    });
    expect(getCurrentActorMock).toHaveBeenCalledWith();
  });

  it("clears the stored key on sign out", async () => {
    window.localStorage.setItem("data-agent-access-token", "existing-key");
    getCurrentActorMock.mockResolvedValue(ACTOR);

    render(<AdminSessionKey />);
    await waitFor(() => screen.getByText("Signed in as Jane Admin"));

    fireEvent.click(screen.getByRole("button", { name: /sign out/i }));

    expect(window.localStorage.getItem("data-agent-access-token")).toBeNull();
    await waitFor(() =>
      expect(screen.getByPlaceholderText("Service API key")).toBeInTheDocument(),
    );
  });
});
