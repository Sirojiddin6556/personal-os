/**
 * @file api-client.ts
 * @description Enterprise-grade HTTP fetch client with RFC 9457 Problem Details,
 * automatic Idempotency-Key generation, optimistic concurrency (ETag/If-Match),
 * and cursor-based pagination helper.
 */

import { PaginatedResponse } from '@/types/domain';

/**
 * Standard RFC 9457 Problem Details object schema.
 */
export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  code?: string;
  invalid_params?: Array<{
    name: string;
    reason: string;
  }>;
  current_version?: number;
  [key: string]: unknown;
}

/**
 * Base API error class wrapping RFC 9457 Problem Details.
 */
export class ApiError extends Error {
  public readonly status: number;
  public readonly problem: ProblemDetails;
  public readonly code?: string;

  constructor(problem: ProblemDetails) {
    super(problem.detail || problem.title || `HTTP Error ${problem.status}`);
    this.name = 'ApiError';
    this.status = problem.status;
    this.problem = problem;
    this.code = problem.code;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Thrown on 409 Conflict (e.g. concurrent mutation or in-flight idempotency lock)
 * or 412 Precondition Failed (optimistic locking concurrency mismatch).
 */
export class ConflictError extends ApiError {
  public readonly currentVersion?: number;

  constructor(problem: ProblemDetails, currentVersion?: number) {
    super(problem);
    this.name = 'ConflictError';
    this.currentVersion = currentVersion ?? problem.current_version;
  }
}

/**
 * Thrown on 412 Precondition Failed (lost update detected by If-Match).
 */
export class PreconditionFailedError extends ConflictError {
  constructor(problem: ProblemDetails, currentVersion?: number) {
    super(problem, currentVersion);
    this.name = 'PreconditionFailedError';
  }
}

/**
 * Thrown on 422 Unprocessable Entity with field-level validation errors.
 */
export class ValidationError extends ApiError {
  public readonly fields: Array<{ name: string; reason: string }>;
  public readonly fieldMap: Record<string, string>;

  constructor(problem: ProblemDetails) {
    super(problem);
    this.name = 'ValidationError';
    this.fields = problem.invalid_params || [];
    this.fieldMap = this.fields.reduce<Record<string, string>>((acc, curr) => {
      acc[curr.name] = curr.reason;
      return acc;
    }, {});
  }
}

/**
 * Options for configuring `apiRequest`.
 */
export interface ApiRequestOptions<TBody = unknown> {
  /** Request body payload */
  body?: TBody;
  /** Custom HTTP headers */
  headers?: Record<string, string>;
  /** URL query parameters */
  params?: Record<string, string | number | boolean | undefined | null>;
  /** Explicit Idempotency-Key (UUIDv4). If omitted for POST/PATCH/DELETE, auto-generated. */
  idempotencyKey?: string;
  /** Version number for optimistic concurrency (sets If-Match: W/"{version}") */
  version?: number | string;
  /** Deprecated alias for version */
  ifMatch?: number | string;
  /** AbortController signal for request cancellation */
  signal?: AbortSignal;
  /** Explicit bearer token (if omitted, extracted from localStorage or cookie) */
  token?: string;
}

/**
 * Base URL for the Core REST API.
 */
export const API_BASE_URL = (() => {
  const envUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8008/v1';
  return envUrl.endsWith('/v1') ? envUrl : `${envUrl}/v1`;
})();

/**
 * Helper to retrieve stored auth token in browser or SSR environment.
 */
function getAuthToken(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }
  try {
    const local = localStorage.getItem('personal_os_access_token');
    if (local) return local;

    // Fallback: parse document.cookie for personal_os_session
    const match = document.cookie.match(/(?:^|;\s*)personal_os_access_token=([^;]+)/);
    if (match) return decodeURIComponent(match[1]);
  } catch {
    // Ignore storage access errors in private mode
  }
  return null;
}

/**
 * Performs a typed HTTP request to the Core REST API.
 *
 * @template TData Expected response data type.
 * @template TBody Request payload type.
 * @param method HTTP verb.
 * @param path Endpoint path (e.g. '/tasks' or '/finance/transactions').
 * @param options Request configuration options.
 * @returns Promise resolving to parsed response JSON or empty object on 204.
 */
export async function apiRequest<TData, TBody = unknown>(
  method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  options: ApiRequestOptions<TBody> = {}
): Promise<TData> {
  const {
    body,
    headers = {},
    params,
    idempotencyKey,
    version,
    ifMatch,
    signal,
    token,
  } = options;

  // 1. Construct endpoint URL and query string
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const fullUrl = `${API_BASE_URL}${cleanPath}`;
  const urlObj = new URL(fullUrl, typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000');

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        urlObj.searchParams.append(key, String(value));
      }
    });
  }

  // 2. Build HTTP request headers
  const requestHeaders: Record<string, string> = {
    Accept: 'application/json',
    ...headers,
  };

  // Bearer authentication
  const authToken = token || getAuthToken();
  if (authToken) {
    requestHeaders['Authorization'] = `Bearer ${authToken}`;
  }

  // Idempotency-Key for mutating requests
  const isMutatingMethod = method === 'POST' || method === 'PATCH' || method === 'DELETE';
  if (isMutatingMethod) {
    if (idempotencyKey) {
      requestHeaders['Idempotency-Key'] = idempotencyKey;
    } else if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      requestHeaders['Idempotency-Key'] = crypto.randomUUID();
    }
  }

  // If-Match ETag for optimistic concurrency
  const effectiveVersion = version !== undefined ? version : ifMatch;
  if (effectiveVersion !== undefined && effectiveVersion !== null) {
    requestHeaders['If-Match'] =
      typeof effectiveVersion === 'number'
        ? `W/"${effectiveVersion}"`
        : String(effectiveVersion);
  }

  // Request body
  let requestBody: string | undefined;
  if (body !== undefined) {
    requestHeaders['Content-Type'] = 'application/json';
    requestBody = JSON.stringify(body);
  }

  // 3. Execute Fetch
  let response: Response;
  try {
    response = await fetch(urlObj.toString(), {
      method,
      headers: requestHeaders,
      body: requestBody,
      signal,
    });
  } catch (networkError) {
    // If request was aborted by client, rethrow
    if (signal?.aborted) {
      throw networkError;
    }
    throw new ApiError({
      type: 'https://api.personal-os.internal/errors/network-error',
      title: 'Network Error',
      status: 0,
      detail: networkError instanceof Error ? networkError.message : 'Network request failed',
    });
  }

  // 4. Handle 204 No Content
  if (response.status === 204) {
    return {} as TData;
  }

  // 5. Handle HTTP Errors (RFC 9457)
  if (!response.ok) {
    let problem: ProblemDetails;
    try {
      problem = (await response.json()) as ProblemDetails;
    } catch {
      problem = {
        type: 'https://api.personal-os.internal/errors/unknown',
        title: response.statusText || 'API Request Failed',
        status: response.status,
        detail: `Request to ${path} failed with HTTP ${response.status}`,
      };
    }

    // 401 Unauthorized: broadcast session expiration
    if (response.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('auth:session_expired'));
    }

    // Extract current version from ETag header if present on 412/409
    const etagHeader = response.headers.get('ETag');
    let extractedVersion: number | undefined;
    if (etagHeader) {
      const match = etagHeader.match(/\d+/);
      if (match) extractedVersion = parseInt(match[0], 10);
    }

    // 409 Conflict
    if (response.status === 409) {
      throw new ConflictError(problem, extractedVersion);
    }

    // 412 Precondition Failed
    if (response.status === 412) {
      throw new PreconditionFailedError(problem, extractedVersion);
    }

    // 422 Unprocessable Entity
    if (response.status === 422) {
      throw new ValidationError(problem);
    }

    throw new ApiError(problem);
  }

  // 6. Parse successful JSON response
  return (await response.json()) as TData;
}

/**
 * Options for cursor-based pagination helper.
 */
export interface FetchPaginatedOptions {
  /** Next cursor string token */
  cursor?: string | null;
  /** Maximum number of records per page (default 50) */
  limit?: number;
  /** Additional query filters */
  filters?: Record<string, string | number | boolean | undefined | null>;
  /** Abort signal */
  signal?: AbortSignal;
}

/**
 * Cursor pagination helper wrapping `apiRequest`.
 *
 * @template TItem Record type.
 * @param path Endpoint path.
 * @param options Pagination filters and cursor.
 */
export async function fetchPaginated<TItem>(
  path: string,
  options: FetchPaginatedOptions = {}
): Promise<PaginatedResponse<TItem>> {
  const { cursor, limit = 50, filters = {}, signal } = options;

  const raw = await apiRequest<any>('GET', path, {
    params: {
      ...filters,
      cursor: cursor || undefined,
      limit,
    },
    signal,
  });

  if (raw && typeof raw === 'object') {
    const items: TItem[] = Array.isArray(raw.items) ? raw.items : Array.isArray(raw) ? raw : [];
    const hasMore = Boolean(raw.has_more ?? raw.pagination?.has_more ?? false);
    const nextCursor = (raw.next_cursor ?? raw.pagination?.next_cursor ?? null) as string | null;
    const prevCursor = (raw.prev_cursor ?? raw.pagination?.prev_cursor ?? null) as string | null;
    const totalCount = (raw.total_count ?? raw.pagination?.total_count) as number | undefined;

    return {
      items,
      pagination: {
        has_more: hasMore,
        next_cursor: nextCursor,
        prev_cursor: prevCursor,
        total_count: totalCount,
      },
    };
  }

  return {
    items: [],
    pagination: {
      has_more: false,
      next_cursor: null,
      prev_cursor: null,
    },
  };
}
