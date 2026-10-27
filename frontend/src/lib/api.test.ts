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

describe("tenancy and planning endpoints", () => {
  it("loads organizations without a CSRF token", async () => {
    const organization = {
      id: 1,
      name: "Demo Org",
      role: "owner",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const { calls } = installFetch(() =>
      jsonResponse({ organizations: [organization] }),
    );
    const { listOrganizations } = await loadApi();

    await expect(listOrganizations()).resolves.toEqual([organization]);

    expect(calls[0].url).toBe("/api/v1/organizations");
    expect(calls[0].init.method).toBe("GET");
    expect(header(calls[0].init, "X-CSRFToken")).toBeNull();
  });

  it("creates a task with a CSRF token and returns the project version", async () => {
    const task = {
      id: 8,
      project_id: 5,
      parent_task_id: null,
      name: "Draft plan",
      description: "",
      status: "not_started",
      duration_work_minutes: 120,
      progress: 0,
      priority: 3,
      constraint_type: "none",
      constraint_date: null,
      estimate_optimistic: null,
      estimate_most_likely: null,
      estimate_pessimistic: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse({ csrf_token: "csrf-1" });
      }
      return jsonResponse({ task, project_version: 2 }, 201);
    });
    const { createTask } = await loadApi();

    await expect(
      createTask(5, { name: "Draft plan", duration_work_minutes: 120 }),
    ).resolves.toEqual({ task, project_version: 2 });

    expect(calls.map((call) => call.url)).toEqual([
      "/api/v1/auth/csrf",
      "/api/v1/projects/5/tasks",
    ]);
    expect(calls[1].init.method).toBe("POST");
    expect(header(calls[1].init, "X-CSRFToken")).toBe("csrf-1");
    expect(requestBody(calls[1].init)).toEqual({
      name: "Draft plan",
      duration_work_minutes: 120,
    });
  });

  it("sends the project version when updating a project", async () => {
    const project = {
      id: 5,
      workspace_id: 2,
      name: "Launch",
      status: "active",
      start_date: null,
      target_finish: null,
      version: 2,
      calendar_id: 9,
      created_by: 7,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse({ csrf_token: "csrf-1" });
      }
      return jsonResponse({ project });
    });
    const { updateProject } = await loadApi();

    await updateProject(5, { version: 1, status: "completed" });

    expect(calls[1].url).toBe("/api/v1/projects/5");
    expect(calls[1].init.method).toBe("PATCH");
    expect(requestBody(calls[1].init)).toEqual({
      version: 1,
      status: "completed",
    });
  });

  it("loads a project schedule without a CSRF token", async () => {
    const schedule = {
      project_id: 5,
      project_version: 2,
      project_start: "2026-01-05",
      requested_start: "2026-01-05",
      start_source: "project",
      target_finish: null,
      project_finish: "2026-01-06",
      project_finish_at: "2026-01-06T17:00+00:00",
      calendar: { id: 9 },
      tasks: [],
      dependencies: [],
      critical_path: [],
      warnings: [],
    };
    const { calls } = installFetch(() => jsonResponse({ schedule }));
    const { getProjectSchedule } = await loadApi();

    await expect(getProjectSchedule(5)).resolves.toEqual(schedule);

    expect(calls[0].url).toBe("/api/v1/projects/5/schedule");
    expect(calls[0].init.method).toBe("GET");
    expect(header(calls[0].init, "X-CSRFToken")).toBeNull();
  });

  it("patches the calendar with a CSRF token and project version", async () => {
    const calendar = {
      id: 9,
      project_id: 5,
      name: "Standard",
      timezone: "UTC",
      weekly_rules: { mon: [["09:00", "17:00"]] },
      exceptions: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    const project = { id: 5, version: 3 };
    const { calls } = installFetch((url) => {
      if (url.endsWith("/auth/csrf")) {
        return jsonResponse({ csrf_token: "csrf-1" });
      }
      return jsonResponse({ calendar, project });
    });
    const { updateProjectCalendar } = await loadApi();

    await expect(
      updateProjectCalendar(5, {
        version: 2,
        timezone: "UTC",
        weekly_rules: { mon: [["09:00", "17:00"]] },
      }),
    ).resolves.toEqual({ calendar, project });

    expect(calls.map((call) => call.url)).toEqual([
      "/api/v1/auth/csrf",
      "/api/v1/projects/5/calendar",
    ]);
    expect(calls[1].init.method).toBe("PATCH");
    expect(header(calls[1].init, "X-CSRFToken")).toBe("csrf-1");
    expect(requestBody(calls[1].init)).toEqual({
      version: 2,
      timezone: "UTC",
      weekly_rules: { mon: [["09:00", "17:00"]] },
    });
  });

  it("adds task filters to the query string", async () => {
    const { calls } = installFetch(() => jsonResponse({ tasks: [] }));
    const { listTasks } = await loadApi();

    await expect(
      listTasks(5, { status: "blocked", parent_task_id: 3, limit: 10 }),
    ).resolves.toEqual([]);

    expect(calls[0].url).toBe(
      "/api/v1/projects/5/tasks?status=blocked&parent_task_id=3&limit=10",
    );
    expect(header(calls[0].init, "X-CSRFToken")).toBeNull();
  });
});

describe("project summary", () => {
  it("loads insights using a read-only authenticated request", async () => {
    const summary = { project_version: 2, task_count: 0, completed_task_count: 0, completion_percent: 0, status_counts: { not_started: 0, in_progress: 0, blocked: 0, completed: 0 }, duration_stats: null };
    const { calls } = installFetch(() => jsonResponse({ summary }));
    const { getProjectSummary } = await loadApi();
    await expect(getProjectSummary(12)).resolves.toEqual(summary);
    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/v1/projects/12/summary");
    expect(calls[0].init.credentials).toBe("same-origin");
    expect(header(calls[0].init, "X-CSRFToken")).toBeNull();
  });
});

it("loads all task pages so the list matches the project summary", async () => {
  const { calls } = installFetch((url) => jsonResponse({
    tasks: url.includes("offset=2") ? [{ id: 3 }] : [{ id: 1 }, { id: 2 }], limit: 2,
  }));
  const { listTasks } = await loadApi();
  await expect(listTasks(12)).resolves.toEqual([{ id: 1 }, { id: 2 }, { id: 3 }]);
  expect(calls.map((call) => call.url)).toEqual(["/api/v1/projects/12/tasks", "/api/v1/projects/12/tasks?offset=2"]);
});
