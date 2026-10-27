import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./lib/api";
import { deferred, jsonResponse } from "./test/fetchMock";
import App from "./App";

const apiMocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  listOrganizations: vi.fn(),
}));

vi.mock("./lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("./lib/api")>();
  return {
    ...actual,
    getMe: apiMocks.getMe,
    login: apiMocks.login,
    logout: apiMocks.logout,
    listOrganizations: apiMocks.listOrganizations,
  };
});

const user = {
  id: 7,
  email: "owner@example.com",
  display_name: "Demo Owner",
};

function healthyResponse() {
  return jsonResponse({
    status: "ok",
    service: "projectpulse-api",
    database: "ok",
  });
}

function stubHealth(response: Response | Promise<Response>) {
  const fetchMock = vi.fn(() => Promise.resolve(response));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  apiMocks.getMe.mockReset().mockResolvedValue(null);
  apiMocks.login.mockReset();
  apiMocks.logout.mockReset();
  apiMocks.listOrganizations.mockReset().mockResolvedValue([]);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("initial load", () => {
  it("shows the loading state while restoring the session", async () => {
    const session = deferred<typeof user | null>();
    apiMocks.getMe.mockReturnValue(session.promise);
    stubHealth(healthyResponse());
    render(<App />);

    expect(screen.getByText("One moment.")).toBeInTheDocument();

    await act(async () => {
      session.resolve(null);
      await session.promise;
    });

    expect(
      await screen.findByRole("button", { name: "Sign in" }),
    ).toBeInTheDocument();
  });

  it("shows the login page and online health when signed out", async () => {
    const fetchMock = stubHealth(healthyResponse());
    render(<App />);

    expect(
      await screen.findByRole("button", { name: "Sign in" }),
    ).toBeInTheDocument();
    expect(await screen.findByText("API connected")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/health");
  });

  it("shows the offline health message when the API is unavailable", async () => {
    stubHealth(Promise.reject(new Error("API is offline")));
    render(<App />);

    expect(
      await screen.findByText("API unavailable — start the backend"),
    ).toBeInTheDocument();
  });

  it("shows the offline health message for a non-OK health response", async () => {
    stubHealth(
      jsonResponse(
        { status: "degraded", service: "projectpulse-api" },
        503,
      ),
    );
    render(<App />);

    expect(
      await screen.findByText("API unavailable — start the backend"),
    ).toBeInTheDocument();
  });

  it("restores an existing session", async () => {
    apiMocks.getMe.mockResolvedValue(user);
    stubHealth(healthyResponse());
    render(<App />);

    expect(await screen.findByText("Demo Owner")).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Organizations" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Sign out" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Sign in" }),
    ).not.toBeInTheDocument();
  });
});

describe("login", () => {
  it("moves from the form to the signed-in view", async () => {
    const browser = userEvent.setup();
    apiMocks.login.mockResolvedValue({
      user,
      csrf_token: "session-token",
    });
    stubHealth(healthyResponse());
    render(<App />);

    await screen.findByRole("button", { name: "Sign in" });
    await browser.type(
      screen.getByLabelText("Password"),
      "CorrectHorse123!",
    );
    await browser.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByText("Demo Owner")).toBeInTheDocument();
    expect(apiMocks.login).toHaveBeenCalledWith(
      "owner@demo.local",
      "CorrectHorse123!",
      false,
    );
  });

  it("shows a login error and stays on the form", async () => {
    const browser = userEvent.setup();
    apiMocks.login.mockRejectedValue(
      new ApiError(
        401,
        "invalid_credentials",
        "Email or password is incorrect.",
      ),
    );
    stubHealth(healthyResponse());
    render(<App />);

    await screen.findByRole("button", { name: "Sign in" });
    await browser.type(
      screen.getByLabelText("Password"),
      "WrongPassword123!",
    );
    await browser.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email or password is incorrect.",
    );
    expect(
      screen.getByRole("button", { name: "Sign in" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Demo Owner")).not.toBeInTheDocument();
  });
});

describe("logout", () => {
  it("returns to the login page after signing out", async () => {
    const browser = userEvent.setup();
    apiMocks.getMe.mockResolvedValue(user);
    apiMocks.logout.mockResolvedValue(undefined);
    stubHealth(healthyResponse());
    render(<App />);

    await screen.findByText("Demo Owner");
    await browser.click(screen.getByRole("button", { name: "Sign out" }));

    expect(
      await screen.findByRole("button", { name: "Sign in" }),
    ).toBeInTheDocument();
    expect(apiMocks.logout).toHaveBeenCalledOnce();
  });

  it("keeps the session visible when logout fails", async () => {
    const browser = userEvent.setup();
    apiMocks.getMe.mockResolvedValue(user);
    apiMocks.logout.mockRejectedValue(new Error("network unavailable"));
    stubHealth(healthyResponse());
    render(<App />);

    await screen.findByText("Demo Owner");
    await browser.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Sign out" }),
      ).toBeEnabled(),
    );
    expect(screen.getByText("Demo Owner")).toBeInTheDocument();
  });
});
