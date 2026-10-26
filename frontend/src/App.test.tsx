import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  sessionStorage.clear();
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/api/v1/auth/me")) return jsonResponse({ user: null });
      if (url.includes("/api/v1/legal")) {
        return jsonResponse({
          operator: "Test operator",
          support_email: "support@example.test",
          hosting_location: "Test region",
          retention_period: "30 days",
          deletion_process: "Contact support",
        });
      }
      return jsonResponse({});
    }),
  );
});

describe("welcome and sample onboarding", () => {
  it("shows blank and guided sample choices after checking the session", async () => {
    render(<App />);

    expect(
      await screen.findByRole("button", { name: /start with a blank workspace/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /try a guided sample/i }),
    ).toBeInTheDocument();
  });

  it("opens a clearly labeled sample with a recovery path to a blank workspace", async () => {
    render(<App />);
    fireEvent.click(
      await screen.findByRole("button", { name: /try a guided sample/i }),
    );

    expect(
      await screen.findByText(/guided sample · you are exploring example data/i),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/Sample data · Northstar Studio/).length).toBeGreaterThan(0);
    expect(
      screen.getByRole("button", { name: /start a blank workspace/i }),
    ).toBeInTheDocument();
  });

  it("starts a blank guest workspace without loading a previous draft", async () => {
    sessionStorage.setItem(
      "projectpulse-guest-workspace",
      JSON.stringify({ shouldNotLoad: true }),
    );
    render(<App />);
    fireEvent.click(
      await screen.findByRole("button", { name: /start with a blank workspace/i }),
    );

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /your workspace awaits/i })).toBeInTheDocument(),
    );
    const savedGuest = JSON.parse(
      sessionStorage.getItem("projectpulse-guest-workspace") ?? "{}",
    ) as { organizations?: unknown[] };
    expect(savedGuest.organizations).toEqual([]);
  });

  it("keeps keyboard focus inside the sign-in dialog and labels it for assistive technology", async () => {
    render(<App />);
    fireEvent.click(await screen.findByRole("button", { name: "Sign in" }));

    const dialog = await screen.findByRole("dialog", { name: "Sign in to your workspace" });
    const closeButton = screen.getByRole("button", { name: "Close" });
    expect(document.activeElement).toBe(closeButton);

    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    const focusable = dialog.querySelectorAll<HTMLElement>(
      'a[href],button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex]:not([tabindex="-1"])',
    );
    expect(document.activeElement).toBe(focusable[focusable.length - 1]);
  });
});

describe("account registration", () => {
  it("shows the verification guidance without attempting an immediate login", async () => {
    const requests: string[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        requests.push(url);
        if (url.includes("/api/v1/auth/me")) return jsonResponse({ user: null });
        if (url.includes("/api/v1/csrf")) return jsonResponse({ token: "csrf-token" });
        if (url.includes("/api/v1/auth/register")) {
          return jsonResponse({ message: "Account created. Check your email to verify it before signing in." }, 201);
        }
        return jsonResponse({});
      }),
    );
    render(<App />);

    fireEvent.click(await screen.findByRole("button", { name: "Create an account" }));
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "New User" } });
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "new@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "CorrectHorse123!" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("status")).toHaveTextContent(/check your email to verify/i);
    expect(screen.getByRole("heading", { name: "Sign in to your workspace" })).toBeInTheDocument();
    expect(requests.some((url) => url.endsWith("/api/v1/auth/login"))).toBe(false);
  });
});
