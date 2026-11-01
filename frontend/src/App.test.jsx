import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App.jsx";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("API health view", () => {
  it("shows available only after a successful health response", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent("API is available");
    expect(fetchMock).toHaveBeenCalledWith("/api/health");
  });

  it("shows an unavailable state when the API request fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("connection refused")));

    render(<App />);

    expect(await screen.findByRole("status")).toHaveTextContent("API is unavailable");
    expect(screen.getByText(/make sure the backend is running/i)).toBeInTheDocument();
  });

  it("retries the health request when asked", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "ok" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await screen.findByText("API is available");
    fireEvent.click(screen.getByRole("button", { name: "Check again" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });
});
