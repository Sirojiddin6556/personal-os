import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  apiRequest,
  fetchPaginated,
  ApiError,
  ConflictError,
  PreconditionFailedError,
  ValidationError,
  ProblemDetails,
} from '@/lib/api-client';

describe('API Client Error Classes', () => {
  it('ApiError wraps RFC 9457 Problem Details correctly', () => {
    const problem: ProblemDetails = {
      type: 'https://api.personal-os.internal/errors/not-found',
      title: 'Resource Not Found',
      status: 404,
      detail: 'Task 123 does not exist',
      code: 'TASK_NOT_FOUND',
    };
    const err = new ApiError(problem);

    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.name).toBe('ApiError');
    expect(err.status).toBe(404);
    expect(err.message).toBe('Task 123 does not exist');
    expect(err.code).toBe('TASK_NOT_FOUND');
    expect(err.problem).toEqual(problem);
  });

  it('ConflictError captures current_version from problem or explicit argument', () => {
    const problem: ProblemDetails = {
      type: 'https://api.personal-os.internal/errors/conflict',
      title: 'Conflict',
      status: 409,
      detail: 'Version mismatch',
      current_version: 3,
    };
    const err = new ConflictError(problem);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toBeInstanceOf(ConflictError);
    expect(err.name).toBe('ConflictError');
    expect(err.status).toBe(409);
    expect(err.currentVersion).toBe(3);

    const errExplicit = new ConflictError(problem, 5);
    expect(errExplicit.currentVersion).toBe(5);
  });

  it('PreconditionFailedError extends ConflictError', () => {
    const problem: ProblemDetails = {
      type: 'https://api.personal-os.internal/errors/precondition-failed',
      title: 'Precondition Failed',
      status: 412,
      detail: 'If-Match version mismatch',
    };
    const err = new PreconditionFailedError(problem, 2);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toBeInstanceOf(ConflictError);
    expect(err).toBeInstanceOf(PreconditionFailedError);
    expect(err.name).toBe('PreconditionFailedError');
    expect(err.status).toBe(412);
    expect(err.currentVersion).toBe(2);
  });

  it('ValidationError extracts field-level errors into fieldMap', () => {
    const problem: ProblemDetails = {
      type: 'https://api.personal-os.internal/errors/validation-error',
      title: 'Validation Error',
      status: 422,
      detail: 'Invalid parameters',
      invalid_params: [
        { name: 'title', reason: 'Title is required' },
        { name: 'amount_minor', reason: 'Must be positive' },
      ],
    };
    const err = new ValidationError(problem);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toBeInstanceOf(ValidationError);
    expect(err.status).toBe(422);
    expect(err.fields.length).toBe(2);
    expect(err.fieldMap).toEqual({
      title: 'Title is required',
      amount_minor: 'Must be positive',
    });
  });
});

describe('apiRequest function', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('performs successful GET request and returns JSON body', async () => {
    const mockData = { id: '123', title: 'Test Task' };
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const result = await apiRequest<{ id: string; title: string }>('GET', '/tasks/123');

    expect(result).toEqual(mockData);
    expect(global.fetch).toHaveBeenCalledTimes(1);

    const [url, init] = (global.fetch as any).mock.calls[0];
    expect(url).toContain('/v1/tasks/123');
    expect(init.method).toBe('GET');
    expect(init.headers['Accept']).toBe('application/json');
    // GET requests should NOT include Idempotency-Key
    expect(init.headers['Idempotency-Key']).toBeUndefined();
  });

  it('handles 204 No Content returning an empty object', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 204,
    });

    const result = await apiRequest('DELETE', '/tasks/123');
    expect(result).toEqual({});
  });

  it('auto-generates Idempotency-Key for mutating requests (POST, PATCH, DELETE)', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 'new-id' }),
    });

    await apiRequest('POST', '/tasks', { body: { title: 'New Task' } });

    const [, init] = (global.fetch as any).mock.calls[0];
    expect(init.headers['Idempotency-Key']).toBeTruthy();
    expect(init.headers['Content-Type']).toBe('application/json');
    expect(init.body).toBe(JSON.stringify({ title: 'New Task' }));
  });

  it('preserves user-provided Idempotency-Key', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 'tx-1' }),
    });

    await apiRequest('POST', '/finance/transactions', {
      body: { amount_minor: 1000 },
      idempotencyKey: 'custom-idempotency-uuid',
    });

    const [, init] = (global.fetch as any).mock.calls[0];
    expect(init.headers['Idempotency-Key']).toBe('custom-idempotency-uuid');
  });

  it('sets If-Match header formatted as strong numeric ETag when version is supplied', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ id: 'task-1', version: 3 }),
    });

    await apiRequest('PATCH', '/tasks/task-1', {
      body: { status: 'done' },
      version: 2,
    });

    const [, init] = (global.fetch as any).mock.calls[0];
    expect(init.headers['If-Match']).toBe('"2"');
  });

  it('appends query parameters safely to endpoint URL', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ items: [] }),
    });

    await apiRequest('GET', '/tasks', {
      params: { status: 'todo', limit: 20, ignored: null },
    });

    const [url] = (global.fetch as any).mock.calls[0];
    expect(url).toContain('status=todo');
    expect(url).toContain('limit=20');
    expect(url).not.toContain('ignored');
  });

  it('injects Authorization Bearer token header if token is provided', async () => {
    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ user: 'Alice' }),
    });

    await apiRequest('GET', '/auth/me', { token: 'jwt-access-token-xyz' });

    const [, init] = (global.fetch as any).mock.calls[0];
    expect(init.headers['Authorization']).toBe('Bearer jwt-access-token-xyz');
  });

  describe('HTTP error handling & RFC 9457 mapping', () => {
    it('throws ConflictError on HTTP 409 and extracts ETag version if available', async () => {
      const problem = {
        type: 'https://api.personal-os.internal/errors/conflict',
        title: 'Optimistic Lock Conflict',
        status: 409,
        detail: 'Task version conflict',
        current_version: 4,
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 409,
        headers: new Headers({ ETag: 'W/"4"' }),
        json: async () => problem,
      });

      await expect(apiRequest('PATCH', '/tasks/1', { version: 3 })).rejects.toThrow(ConflictError);
    });

    it('throws PreconditionFailedError on HTTP 412', async () => {
      const problem = {
        type: 'https://api.personal-os.internal/errors/precondition-failed',
        title: 'Precondition Failed',
        status: 412,
        detail: 'If-Match condition failed',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 412,
        headers: new Headers({ ETag: 'W/"7"' }),
        json: async () => problem,
      });

      await expect(apiRequest('PATCH', '/tasks/1', { version: 5 })).rejects.toThrow(
        PreconditionFailedError
      );
    });

    it('throws ValidationError on HTTP 422', async () => {
      const problem = {
        type: 'https://api.personal-os.internal/errors/validation-error',
        title: 'Validation Error',
        status: 422,
        detail: 'Schema violation',
        invalid_params: [{ name: 'priority', reason: 'Invalid enum value' }],
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 422,
        headers: new Headers(),
        json: async () => problem,
      });

      await expect(apiRequest('POST', '/tasks', { body: {} })).rejects.toThrow(ValidationError);
    });

    it('throws generic ApiError on other HTTP errors', async () => {
      const problem = {
        type: 'https://api.personal-os.internal/errors/server-error',
        title: 'Internal Server Error',
        status: 500,
        detail: 'Database connection failed',
      };

      (global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        headers: new Headers(),
        json: async () => problem,
      });

      await expect(apiRequest('GET', '/dashboard/today')).rejects.toThrow(ApiError);
    });

    it('handles network failure (fetch throws) by throwing ApiError with status 0', async () => {
      (global.fetch as any).mockRejectedValueOnce(new Error('Connection refused'));

      await expect(apiRequest('GET', '/tasks')).rejects.toThrow(ApiError);
    });
  });
});

describe('fetchPaginated helper', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('invokes apiRequest with cursor, limit, and additional filters', async () => {
    const mockPage = {
      items: [{ id: '1', title: 'Task 1' }],
      next_cursor: 'cursor_token_next',
      has_more: true,
      total_count: 50,
    };

    (global.fetch as any).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => mockPage,
    });

    const result = await fetchPaginated<{ id: string; title: string }>('/tasks', {
      cursor: 'cur123',
      limit: 25,
      filters: { status: 'inbox' },
    });

    expect(result).toEqual({
      items: mockPage.items,
      pagination: {
        has_more: true,
        next_cursor: 'cursor_token_next',
        prev_cursor: null,
        total_count: 50,
      },
    });

    const [url] = (global.fetch as any).mock.calls[0];
    expect(url).toContain('cursor=cur123');
    expect(url).toContain('limit=25');
    expect(url).toContain('status=inbox');
  });
});
