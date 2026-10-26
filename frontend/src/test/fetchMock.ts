import { vi } from "vitest";

export type FetchCall = {
  url: string;
  init: RequestInit;
};

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export function textResponse(body: string, status = 500): Response {
  return new Response(body, {
    status,
    headers: { "Content-Type": "text/plain" },
  });
}

export function installFetch(
  handler: (
    url: string,
    init: RequestInit,
    index: number,
  ) => Response | Promise<Response>,
) {
  const calls: FetchCall[] = [];

  const fetchMock = vi.fn(
    (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.toString()
            : input.url;

      calls.push({ url, init });
      return Promise.resolve(handler(url, init, calls.length - 1));
    },
  );

  vi.stubGlobal("fetch", fetchMock);

  return { calls, fetchMock };
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;

  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
}

export function header(init: RequestInit, name: string): string | null {
  return new Headers(init.headers).get(name);
}

export function requestBody(init: RequestInit): unknown {
  return typeof init.body === "string" ? JSON.parse(init.body) : init.body;
}
