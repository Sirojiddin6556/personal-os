/**
 * @file query-client.ts
 * @description Central QueryClient singleton with default caching policies,
 * retry strategies excluding 401/403/404/422 errors, and stale times.
 */

import { QueryClient } from '@tanstack/react-query';
import { ApiError } from './api-client';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds fresh
      gcTime: 1000 * 60 * 10, // 10 minutes memory retention
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          // Do not retry authorization, forbidden, not found, or client validation errors
          if ([401, 403, 404, 422].includes(error.status)) {
            return false;
          }
        }
        return failureCount < 3;
      },
    },
    mutations: {
      retry: 1,
    },
  },
});
