import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../lib/api";
import { deferred } from "../test/fetchMock";
import LoginPage from "./LoginPage";

const authMocks = vi.hoisted(() => ({
  login: vi.fn(),
}));

vi.mock("../auth/AuthContext", () => ({
  useAuth: () => authMocks,
}));

type HealthState = "loading" | "online" | "offline";

function renderPage(
  props: { health?: HealthState; status?: string } = {},
) {
  return render(
    <LoginPage
      health={props.health ?? "online"}
      status={props.status ?? "API connected"}
    />,
  );
}

beforeEach(() => {
  authMocks.login.mockReset();
});

describe("layout", () => {
  it("renders the demo defaults and accessible field attributes", () => {
    const { container } = renderPage();

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      /pick up/i,
    );

    const email = screen.getByLabelText("Email");
    expect(email).toHaveValue("owner@demo.local");
    expect(email).toHaveAttribute("type", "email");
    expect(email).toHaveAttribute("autocomplete", "username");
    expect(email).toBeRequired();

    const password = screen.getByLabelText("Password");
    expect(password).toHaveValue("");
    expect(password).toHaveAttribute("type", "password");
    expect(password).toHaveAttribute("autocomplete", "current-password");
    expect(password).toBeRequired();

    expect(
      screen.getByRole("checkbox", { name: /keep me signed in/i }),
    ).not.toBeChecked();
    expect(screen.getByText(/demo accounts:/i)).toBeInTheDocument();
    expect(screen.getByText("API connected")).toBeInTheDocument();
    expect(container.querySelector(".dot.online")).not.toBeNull();
  });

  it("renders loading and offline health states", () => {
    const { container, rerender } = renderPage();

    rerender(
      <LoginPage
        health="offline"
        status="API unavailable — start the backend"
      />,
    );
    expect(container.querySelector(".dot.offline")).not.toBeNull();
    expect(
      screen.getByText("API unavailable — start the backend"),
    ).toBeInTheDocument();

    rerender(<LoginPage health="loading" status="Connecting to API…" />);
    expect(container.querySelector(".dot.online")).toBeNull();
    expect(container.querySelector(".dot.offline")).toBeNull();
    expect(screen.getByText("Connecting to API…")).toBeInTheDocument();
  });
});

describe("submission", () => {
  it("submits the entered values and unchecked remember flag", async () => {
    const user = userEvent.setup();
    authMocks.login.mockResolvedValue(undefined);
    renderPage();

    await user.type(
      screen.getByLabelText("Password"),
      "CorrectHorse123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(authMocks.login).toHaveBeenCalledWith(
        "owner@demo.local",
        "CorrectHorse123!",
        false,
      ),
    );
  });

  it("submits an edited email address", async () => {
    const user = userEvent.setup();
    authMocks.login.mockResolvedValue(undefined);
    renderPage();

    const email = screen.getByLabelText("Email");
    await user.clear(email);
    await user.type(email, "other@example.com");
    await user.type(
      screen.getByLabelText("Password"),
      "CorrectHorse123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(authMocks.login).toHaveBeenCalledWith(
        "other@example.com",
        "CorrectHorse123!",
        false,
      ),
    );
  });

  it("passes the remember choice to the auth context", async () => {
    const user = userEvent.setup();
    authMocks.login.mockResolvedValue(undefined);
    renderPage();

    await user.type(
      screen.getByLabelText("Password"),
      "CorrectHorse123!",
    );
    await user.click(
      screen.getByRole("checkbox", { name: /keep me signed in/i }),
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(authMocks.login).toHaveBeenCalledWith(
        "owner@demo.local",
        "CorrectHorse123!",
        true,
      ),
    );
  });

  it("disables the button while the request is pending", async () => {
    const user = userEvent.setup();
    const pending = deferred<void>();
    authMocks.login.mockReturnValue(pending.promise);
    renderPage();

    await user.type(
      screen.getByLabelText("Password"),
      "CorrectHorse123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      screen.getByRole("button", { name: "Signing in…" }),
    ).toBeDisabled();

    pending.resolve();

    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "Sign in" }),
      ).toBeEnabled(),
    );
  });
});

describe("errors", () => {
  it("shows the API error message and re-enables the button", async () => {
    const user = userEvent.setup();
    authMocks.login.mockRejectedValue(
      new ApiError(
        401,
        "invalid_credentials",
        "Email or password is incorrect.",
      ),
    );
    renderPage();

    await user.type(
      screen.getByLabelText("Password"),
      "WrongPassword123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Email or password is incorrect.",
    );
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });

  it("shows a generic message for unexpected failures", async () => {
    const user = userEvent.setup();
    authMocks.login.mockRejectedValue(new Error("network unavailable"));
    renderPage();

    await user.type(
      screen.getByLabelText("Password"),
      "CorrectHorse123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to sign in right now.",
    );
  });

  it("clears the previous error on retry", async () => {
    const user = userEvent.setup();
    authMocks.login
      .mockRejectedValueOnce(
        new ApiError(
          401,
          "invalid_credentials",
          "Email or password is incorrect.",
        ),
      )
      .mockResolvedValueOnce(undefined);
    renderPage();

    await user.type(
      screen.getByLabelText("Password"),
      "WrongPassword123!",
    );
    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() =>
      expect(screen.queryByRole("alert")).not.toBeInTheDocument(),
    );
  });
});
