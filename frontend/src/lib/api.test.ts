import { afterEach, describe, expect, it, vi } from "vitest";

import {
  deferred,
  header,
  installFetch,
  jsonResponse,
  requestBody,
  textResponse,
} from "../test/fetchMock";

const user = {
  id: 7,
  email: "owner@example.com",
  display_name: "Owner",
};
const authResponse = { user, csrf_token: "session-token" };

async function loadApi() {
  vi.resetModules();
  return import("./api");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getMe", () => {
  it("returns the current user with same-origin credentials", async () => {
    const { calls } = installFetch(() => jsonResponse({ user }));
    const { getMe } = await loadApi();

    await expect(getMe()).resolves.toEqual(user);

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/v1/auth/me");
    expect(calls[0].init.method).toBe("GET");
    expect(calls[0].init.credentials).toBe("same-origin");
    expect(header(calls[0].init, "X-CSRFToken")).toBeNull();
  });
});

describe("login", () => {
  it("fetches a CSRF token before sending the JSON body", async () => {
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse({ csrf_token: "csrf-1" });
      }
      if (url.endsWith("/auth/login")) {
        return jsonResponse(authResponse);
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    const { login } = await loadApi();

    await expect(
      login("owner@example.com", "CorrectHorse123!", true),
    ).resolves.toEqual(authResponse);

    expect(calls.map((call) => call.url)).toEqual([
      "/api/v1/auth/csrf",
      "/api/v1/auth/login",
    ]);

    const request = calls[1];
    expect(request.init.method).toBe("POST");
    expect(request.init.credentials).toBe("same-origin");
    expect(header(request.init, "X-CSRFToken")).toBe("csrf-1");
    expect(header(request.init, "Content-Type")).toBe("application/json");
    expect(requestBody(request.init)).toEqual({
      email: "owner@example.com",
      password: "CorrectHorse123!",
      remember: true,
    });
  });

  it("reuses the login token for logout and clears it afterward", async () => {
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse({ csrf_token: "csrf-1" });
      }
      if (url.endsWith("/auth/login")) {
        return jsonResponse(authResponse);
      }
      if (url.endsWith("/auth/logout")) {
        return jsonResponse({ status: "ok" });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    const api = await loadApi();

    await api.login("owner@example.com", "CorrectHorse123!", false);
    await api.logout();

    expect(calls.map((call) => call.url)).toEqual([
      "/api/v1/auth/csrf",
      "/api/v1/auth/login",
      "/api/v1/auth/logout",
    ]);
    expect(header(calls[2].init, "X-CSRFToken")).toBe("session-token");

    await api.login("owner@example.com", "CorrectHorse123!", false);

    expect(
      calls.filter((call) => call.url.endsWith("/auth/csrf")),
    ).toHaveLength(2);
  });
});

describe("register", () => {
  it("sends the display name as display_name", async () => {
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse({ csrf_token: "csrf-1" });
      }
      if (url.endsWith("/auth/register")) {
        return jsonResponse(authResponse, 201);
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    const { register } = await loadApi();

    await expect(
      register("new@example.com", "CorrectHorse123!", "New User"),
    ).resolves.toEqual(authResponse);

    expect(requestBody(calls[1].init)).toEqual({
      email: "new@example.com",
      password: "CorrectHorse123!",
      display_name: "New User",
    });
  });
});

describe("logout", () => {
  it("accepts an empty response and clears the cached token", async () => {
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse({ csrf_token: "csrf-1" });
      }
      if (url.endsWith("/auth/login")) {
        return jsonResponse(authResponse);
      }
      if (url.endsWith("/auth/logout")) {
        return new Response(null, { status: 204 });
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    const api = await loadApi();

    await api.login("owner@example.com", "CorrectHorse123!", false);
    await expect(api.logout()).resolves.toBeUndefined();

    await api.login("owner@example.com", "CorrectHorse123!", false);

    expect(
      calls.filter((call) => call.url.endsWith("/auth/csrf")),
    ).toHaveLength(2);
  });
});

describe("errors", () => {
  it("maps the API error envelope to ApiError", async () => {
    installFetch(() =>
      jsonResponse(
        {
          error: {
            code: "unauthorized",
            message: "Authentication is required.",
            details: { reason: "missing session" },
            request_id: "req-1",
          },
        },
        401,
      ),
    );
    const { getMe } = await loadApi();

    await expect(getMe()).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      code: "unauthorized",
      message: "Authentication is required.",
      details: { reason: "missing session" },
      requestId: "req-1",
    });
  });

  it("falls back to a generic error for non-JSON failures", async () => {
    installFetch(() => textResponse("server exploded", 500));
    const { getMe } = await loadApi();

    await expect(getMe()).rejects.toMatchObject({
      status: 500,
      code: "http_error",
      message: "The request could not be completed.",
    });
  });

  it("does not send the mutation when the CSRF request fails", async () => {
    let loginCalls = 0;
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse(
          { error: { code: "internal_error", message: "Unavailable." } },
          500,
        );
      }
      loginCalls += 1;
      return jsonResponse(authResponse);
    });
    const { login } = await loadApi();

    await expect(
      login("owner@example.com", "CorrectHorse123!", false),
    ).rejects.toMatchObject({ status: 500, code: "internal_error" });

    expect(loginCalls).toBe(0);
    expect(calls).toHaveLength(1);
  });
});

describe("CSRF retry", () => {
  it("retries once with a fresh token", async () => {
    let loginAttempts = 0;
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse({ csrf_token: "fresh-token" });
      }
      if (url.endsWith("/auth/login")) {
        loginAttempts += 1;
        if (loginAttempts === 1) {
          return jsonResponse(
            {
              error: {
                code: "csrf_error",
                message: "Invalid or missing CSRF token.",
              },
            },
            400,
          );
        }
        return jsonResponse(authResponse);
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    const { login } = await loadApi();

    await expect(
      login("owner@example.com", "CorrectHorse123!", false),
    ).resolves.toEqual(authResponse);

    expect(loginAttempts).toBe(2);
    expect(calls.map((call) => call.url)).toEqual([
      "/api/v1/auth/csrf",
      "/api/v1/auth/login",
      "/api/v1/auth/csrf",
      "/api/v1/auth/login",
    ]);
    expect(header(calls[3].init, "X-CSRFToken")).toBe("fresh-token");
  });

  it("stops after one retry when the fresh token also fails", async () => {
    let loginAttempts = 0;
    installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse({ csrf_token: "csrf-token" });
      }
      loginAttempts += 1;
      return jsonResponse(
        {
          error: {
            code: "csrf_error",
            message: "Invalid or missing CSRF token.",
          },
        },
        400,
      );
    });
    const { login } = await loadApi();

    await expect(
      login("owner@example.com", "CorrectHorse123!", false),
    ).rejects.toMatchObject({ code: "csrf_error", status: 400 });

    expect(loginAttempts).toBe(2);
  });

  it("shares one in-flight CSRF request between mutations", async () => {
    const csrfResponse = deferred<Response>();
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return csrfResponse.promise;
      }
      if (url.endsWith("/auth/login")) {
        return jsonResponse(authResponse);
      }
      throw new Error(`Unexpected URL: ${url}`);
    });
    const { login } = await loadApi();

    const first = login("owner@example.com", "CorrectHorse123!", false);
    const second = login("owner@example.com", "CorrectHorse123!", false);

    expect(
      calls.filter((call) => call.url.endsWith("/auth/csrf")),
    ).toHaveLength(1);

    csrfResponse.resolve(jsonResponse({ csrf_token: "shared-token" }));
    await Promise.all([first, second]);

    const loginCalls = calls.filter((call) => call.url.endsWith("/login"));
    expect(loginCalls).toHaveLength(2);
    expect(
      loginCalls.every(
        (call) => header(call.init, "X-CSRFToken") === "shared-token",
      ),
    ).toBe(true);
  });
});
