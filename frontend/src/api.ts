import type { ApiErrorBody } from "./types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

let accessToken: string | null = null;
let refreshPromise: Promise<string | null> | null = null;

export class ApiError extends Error {
  status: number;
  code: string;
  fields: ApiErrorBody["error"]["fields"];

  constructor(status: number, body?: ApiErrorBody) {
    super(body?.error.message ?? "The request could not be completed.");
    this.status = status;
    this.code = body?.error.code ?? "REQUEST_ERROR";
    this.fields = body?.error.fields ?? {};
  }
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

async function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
    })
      .then(async (response) => {
        if (!response.ok) return null;
        const body = (await response.json()) as { data: { accessToken: string } };
        setAccessToken(body.data.accessToken);
        return body.data.accessToken;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  retryAuth?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let body: BodyInit | undefined;
  if (options.body instanceof FormData) {
    body = options.body;
  } else if (options.body !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(options.body);
  }
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    body,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && options.retryAuth !== false) {
    const token = await refreshAccessToken();
    if (token) return apiRequest<T>(path, { ...options, retryAuth: false });
  }
  if (!response.ok) {
    let errorBody: ApiErrorBody | undefined;
    try {
      errorBody = (await response.json()) as ApiErrorBody;
    } catch {
      errorBody = undefined;
    }
    throw new ApiError(response.status, errorBody);
  }
  if (response.status === 204) return undefined as T;
  const payload = (await response.json()) as { data: T; meta?: unknown };
  return payload.data;
}

export async function apiPage<T>(path: string): Promise<{
  data: T[];
  meta: { page: number; pageSize: number; total: number; totalPages: number };
}> {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let response = await fetch(`${API_BASE}${path}`, { headers, credentials: "include" });
  if (response.status === 401 && (await refreshAccessToken())) {
    headers.set("Authorization", `Bearer ${accessToken}`);
    response = await fetch(`${API_BASE}${path}`, { headers, credentials: "include" });
  }
  if (!response.ok) {
    const body = (await response.json().catch(() => undefined)) as ApiErrorBody | undefined;
    throw new ApiError(response.status, body);
  }
  return response.json();
}

export async function downloadAuthenticated(path: string, filename: string) {
  const headers = new Headers();
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
  let response = await fetch(`${API_BASE}${path}`, { headers, credentials: "include" });
  if (response.status === 401 && (await refreshAccessToken())) {
    headers.set("Authorization", `Bearer ${accessToken}`);
    response = await fetch(`${API_BASE}${path}`, { headers, credentials: "include" });
  }
  if (!response.ok) throw new ApiError(response.status);
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
