export type User = {
  id: number;
  email: string;
  display_name: string;
};

export type AuthResponse = {
  user: User;
  csrf_token: string;
};

type ErrorBody = {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
    request_id?: string;
  };
};

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;
  requestId?: string;

  constructor(
    status: number,
    code: string,
    message: string,
    details?: unknown,
    requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

const API_BASE = "/api/v1";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

let csrfToken: string | null = null;
let csrfRequest: Promise<string> | null = null;

async function parseError(response: Response): Promise<ApiError> {
  let body: ErrorBody | null = null;
  try {
    body = (await response.json()) as ErrorBody;
  } catch {
    body = null;
  }

  const error = body?.error;
  return new ApiError(
    response.status,
    error?.code ?? "http_error",
    error?.message ?? "The request could not be completed.",
    error?.details,
    error?.request_id,
  );
}

async function readBody<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

async function fetchCsrfToken(force = false): Promise<string> {
  if (force) {
    csrfToken = null;
  }
  if (csrfToken) {
    return csrfToken;
  }
  if (csrfRequest) {
    return csrfRequest;
  }

  csrfRequest = (async () => {
    const response = await fetch(`${API_BASE}/auth/csrf`, {
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw await parseError(response);
    }
    const body = (await response.json()) as { csrf_token: string };
    csrfToken = body.csrf_token;
    return csrfToken;
  })();

  try {
    return await csrfRequest;
  } finally {
    csrfRequest = null;
  }
}

export async function request<T>(
  path: string,
  init: RequestInit = {},
  allowRetry = true,
): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);

  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (!SAFE_METHODS.has(method)) {
    headers.set("X-CSRFToken", await fetchCsrfToken());
  }

  let response = await fetch(`${API_BASE}${path}`, {
    ...init,
    method,
    headers,
    credentials: "same-origin",
  });

  if (response.ok) {
    const body = await readBody<T>(response);
    if (path === "/auth/login" || path === "/auth/register") {
      const token = (body as { csrf_token?: string } | undefined)?.csrf_token;
      if (token) csrfToken = token;
    }
    if (path === "/auth/logout") csrfToken = null;
    return body;
  }

  const error = await parseError(response);
  if (error.code === "csrf_error" && allowRetry && !SAFE_METHODS.has(method)) {
    headers.set("X-CSRFToken", await fetchCsrfToken(true));
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      method,
      headers,
      credentials: "same-origin",
    });
    if (response.ok) {
      const body = await readBody<T>(response);
      if (path === "/auth/login" || path === "/auth/register") {
        const token = (body as { csrf_token?: string } | undefined)?.csrf_token;
        if (token) csrfToken = token;
      }
      if (path === "/auth/logout") csrfToken = null;
      return body;
    }
    throw await parseError(response);
  }

  throw error;
}

export async function getMe(): Promise<User> {
  const body = await request<{ user: User }>("/auth/me");
  return body.user;
}

export async function login(
  email: string,
  password: string,
  remember: boolean,
): Promise<AuthResponse> {
  const body = await request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password, remember }),
  });
  csrfToken = body.csrf_token;
  return body;
}

export async function register(
  email: string,
  password: string,
  displayName: string,
): Promise<AuthResponse> {
  const body = await request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      display_name: displayName,
    }),
  });
  csrfToken = body.csrf_token;
  return body;
}

export async function logout(): Promise<void> {
  try {
    await request<{ status: string }>("/auth/logout", { method: "POST" });
  } finally {
    csrfToken = null;
  }
}
