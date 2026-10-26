import { act, render, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../lib/api";
import { deferred } from "../test/fetchMock";
import { AuthProvider, useAuth } from "./AuthContext";

const apiMocks = vi.hoisted(() => ({
  getMe: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}));

vi.mock("../lib/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/api")>();
  return {
    ...actual,
    getMe: apiMocks.getMe,
    login: apiMocks.login,
    logout: apiMocks.logout,
  };
});

const user = {
  id: 7,
  email: "owner@example.com",
  display_name: "Owner",
};

function renderAuth() {
  return renderHook(() => useAuth(), { wrapper: AuthProvider });
}

beforeEach(() => {
  apiMocks.getMe.mockReset().mockResolvedValue(null);
  apiMocks.login.mockReset();
  apiMocks.logout.mockReset();
});

describe("session loading", () => {
  it("starts loading and then exposes the current user", async () => {
    const session = deferred<typeof user | null>();
    apiMocks.getMe.mockReturnValue(session.promise);
    const { result } = renderAuth();

    expect(result.current.loading).toBe(true);

    await act(async () => {
      session.resolve(user);
      await session.promise;
    });

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.user).toEqual(user);
  });

  it("quietly clears the user when the session is unauthorized", async () => {
    apiMocks.getMe.mockRejectedValue(
      new ApiError(401, "unauthorized", "Authentication is required."),
    );
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.user).toBeNull();
    expect(errorSpy).not.toHaveBeenCalled();
  });

  it("logs unexpected session failures", async () => {
    const failure = new ApiError(500, "internal_error", "Server unavailable.");
    apiMocks.getMe.mockRejectedValue(failure);
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    const { result } = renderAuth();

    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.user).toBeNull();
    expect(errorSpy).toHaveBeenCalledWith(
      "Failed to load the current session",
      failure,
    );
  });
});

describe("login", () => {
  it("stores the user returned by the API", async () => {
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));

    apiMocks.login.mockResolvedValue({
      user,
      csrf_token: "session-token",
    });

    await act(async () => {
      await result.current.login("owner@example.com", "CorrectHorse123!", true);
    });

    expect(apiMocks.login).toHaveBeenCalledWith(
      "owner@example.com",
      "CorrectHorse123!",
      true,
    );
    expect(result.current.user).toEqual(user);
  });

  it("propagates login failures without setting a user", async () => {
    const failure = new ApiError(
      401,
      "invalid_credentials",
      "Email or password is incorrect.",
    );
    apiMocks.login.mockRejectedValue(failure);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));

    let caught: unknown;
    await act(async () => {
      try {
        await result.current.login(
          "owner@example.com",
          "WrongPassword123!",
          false,
        );
      } catch (error) {
        caught = error;
      }
    });

    expect(caught).toBe(failure);
    expect(result.current.user).toBeNull();
  });
});

describe("logout", () => {
  it("clears the user after the API succeeds", async () => {
    apiMocks.getMe.mockResolvedValue(user);
    apiMocks.logout.mockResolvedValue(undefined);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(user));

    await act(async () => {
      await result.current.logout();
    });

    expect(apiMocks.logout).toHaveBeenCalledOnce();
    expect(result.current.user).toBeNull();
  });

  it("keeps the user when the API fails", async () => {
    const failure = new Error("network unavailable");
    apiMocks.getMe.mockResolvedValue(user);
    apiMocks.logout.mockRejectedValue(failure);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.user).toEqual(user));

    let caught: unknown;
    await act(async () => {
      try {
        await result.current.logout();
      } catch (error) {
        caught = error;
      }
    });

    expect(caught).toBe(failure);
    expect(result.current.user).toEqual(user);
  });
});

describe("refresh", () => {
  it("reloads the current user", async () => {
    apiMocks.getMe
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(user);
    const { result } = renderAuth();
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.user).toEqual(user);
  });
});

describe("useAuth", () => {
  it("requires an AuthProvider", () => {
    function Consumer() {
      useAuth();
      return null;
    }

    vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<Consumer />)).toThrow(
      "useAuth must be used inside AuthProvider",
    );
  });
});
