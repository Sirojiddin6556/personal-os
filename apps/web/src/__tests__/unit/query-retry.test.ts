import { describe, it, expect } from 'vitest';
import { queryClient } from '@/lib/query-client';
import { ApiError, ProblemDetails } from '@/lib/api-client';

describe('QueryClient Retry and Caching Strategy', () => {
  const queryOptions = queryClient.getDefaultOptions().queries;
  const retryFn = queryOptions?.retry as (failureCount: number, error: unknown) => boolean;

  it('configures sensible staleTime and gcTime defaults', () => {
    expect(queryOptions?.staleTime).toBe(30_000); // 30s fresh
    expect(queryOptions?.gcTime).toBe(600_000); // 10m cache retention
    expect(queryOptions?.refetchOnWindowFocus).toBe(true);
    expect(queryOptions?.refetchOnReconnect).toBe(true);
  });

  describe('smart retry policy for ApiErrors', () => {
    const makeApiError = (status: number): ApiError => {
      const problem: ProblemDetails = {
        type: `https://api.personal-os.internal/errors/http-${status}`,
        title: `Error ${status}`,
        status,
        detail: `Sample error ${status}`,
      };
      return new ApiError(problem);
    };

    it('immediately aborts retry for 401 Unauthorized', () => {
      const err = makeApiError(401);
      expect(retryFn(0, err)).toBe(false);
      expect(retryFn(1, err)).toBe(false);
    });

    it('immediately aborts retry for 403 Forbidden', () => {
      const err = makeApiError(403);
      expect(retryFn(0, err)).toBe(false);
      expect(retryFn(1, err)).toBe(false);
    });

    it('immediately aborts retry for 404 Not Found', () => {
      const err = makeApiError(404);
      expect(retryFn(0, err)).toBe(false);
      expect(retryFn(1, err)).toBe(false);
    });

    it('immediately aborts retry for 422 Unprocessable Entity (validation error)', () => {
      const err = makeApiError(422);
      expect(retryFn(0, err)).toBe(false);
      expect(retryFn(1, err)).toBe(false);
    });

    it('retries server errors (500, 502, 503) up to 3 times', () => {
      const err = makeApiError(500);
      expect(retryFn(0, err)).toBe(true);
      expect(retryFn(1, err)).toBe(true);
      expect(retryFn(2, err)).toBe(true);
      expect(retryFn(3, err)).toBe(false); // Max attempts reached
    });

    it('retries non-ApiError exceptions (e.g. TypeError, network drops) up to 3 times', () => {
      const netError = new TypeError('Failed to fetch');
      expect(retryFn(0, netError)).toBe(true);
      expect(retryFn(1, netError)).toBe(true);
      expect(retryFn(2, netError)).toBe(true);
      expect(retryFn(3, netError)).toBe(false);
    });
  });
});
