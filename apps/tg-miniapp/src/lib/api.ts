/** Minimal API client: same-origin /api/* (nginx → FastAPI /v1/*). */

const BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api';

export interface Session {
  token: string;
  workspaceId: string;
  fullName: string;
}

let session: Session | null = null;
let onUnauthorized: (() => void) | null = null;

export function setSession(s: Session | null): void {
  session = s;
}
export function setUnauthorizedHandler(fn: () => void): void {
  onUnauthorized = fn;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string | undefined,
    message: string,
    public body: unknown,
  ) {
    super(message);
  }
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  /** Skip the Authorization header (login endpoints). */
  anonymous?: boolean;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json', ...opts.headers };
  if (opts.body !== undefined) headers['Content-Type'] = 'application/json';
  if (session && !opts.anonymous) {
    headers.Authorization = `Bearer ${session.token}`;
    headers['X-Workspace-Id'] = session.workspaceId;
  }

  const res = await fetch(`${BASE}${path}`, {
    method: opts.method ?? (opts.body !== undefined ? 'POST' : 'GET'),
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });

  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = undefined;
  try {
    data = text ? JSON.parse(text) : undefined;
  } catch {
    data = text;
  }

  if (!res.ok) {
    if (res.status === 401 && !opts.anonymous) onUnauthorized?.();
    const d = (data ?? {}) as { detail?: unknown; code?: string; title?: string };
    const message =
      typeof d.detail === 'string' ? d.detail : d.title ?? `Ошибка ${res.status}`;
    throw new ApiError(res.status, d.code, message, data);
  }
  return data as T;
}

export function newIdempotencyKey(): string {
  return crypto.randomUUID();
}
