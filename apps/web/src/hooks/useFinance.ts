/**
 * @file useFinance.ts
 * @description TanStack Query hooks for managing financial accounts, transaction ledger,
 * monthly category budgets, and the composite Today dashboard summary.
 */

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
  InfiniteData,
} from '@tanstack/react-query';
import { apiRequest, fetchPaginated } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import {
  Account,
  Budget,
  DashboardToday,
  PaginatedResponse,
  Transaction,
  TransactionType,
} from '@/types/domain';

export interface TransactionFilters {
  account_id?: string;
  category_id?: string;
  type?: TransactionType | string;
  from?: string;
  to?: string;
  limit?: number;
}

export interface CreateTransactionInput {
  account_id: string;
  destination_account_id?: string | null;
  category_id?: string | null;
  amount_minor: number;
  currency?: string;
  type: TransactionType;
  description: string;
  transaction_date?: string;
  is_cleared?: boolean;
}

/**
 * Hook to retrieve the list of all financial accounts and their current balances.
 */
export function useAccounts() {
  const query = useQuery<Account[], Error>({
    queryKey: queryKeys.finance.accounts(),
    queryFn: () => apiRequest<Account[]>('GET', '/finance/accounts'),
  });

  return {
    accounts: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Hook to retrieve an infinite cursor-paginated stream of transactions.
 */
export function useTransactions(filters?: TransactionFilters) {
  const query = useInfiniteQuery<PaginatedResponse<Transaction>, Error>({
    queryKey: queryKeys.finance.transactions(filters as Record<string, unknown>),
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) =>
      fetchPaginated<Transaction>('/finance/transactions', {
        cursor: (pageParam as string | null) || undefined,
        limit: filters?.limit || 50,
        filters: filters as Record<string, string | number | boolean | undefined>,
      }),
    getNextPageParam: (lastPage) =>
      lastPage.pagination.has_more ? lastPage.pagination.next_cursor : undefined,
  });

  const transactions: Transaction[] =
    query.data?.pages.flatMap((page) => page.items) ?? [];

  return {
    transactions,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    fetchNextPage: query.fetchNextPage,
    hasNextPage: query.hasNextPage,
    isFetchingNextPage: query.isFetchingNextPage,
    refetch: query.refetch,
  };
}

/**
 * Mutation hook for recording a financial transaction with optimistic ledger append
 * and automatic account balance adjustment.
 */
export function useCreateTransaction() {
  const queryClient = useQueryClient();

  return useMutation<
    Transaction,
    Error,
    CreateTransactionInput,
    {
      previousAccounts?: Account[];
      previousTransactions?: Array<[readonly unknown[], unknown]>;
    }
  >({
    mutationFn: (input: CreateTransactionInput) =>
      apiRequest<Transaction, CreateTransactionInput>(
        'POST',
        '/finance/transactions',
        { body: input }
      ),
    onMutate: async (newTxInput) => {
      // 1. Cancel in-flight queries
      await queryClient.cancelQueries({ queryKey: queryKeys.finance.all });

      // 2. Snapshot current state for rollback
      const previousAccounts = queryClient.getQueryData<Account[]>(
        queryKeys.finance.accounts()
      );
      const txQueries = queryClient.getQueriesData<
        InfiniteData<PaginatedResponse<Transaction>>
      >({
        queryKey: queryKeys.finance.all,
      });
      const previousTransactions = txQueries.map(
        ([key, data]) => [key, data] as [readonly unknown[], unknown]
      );

      // 3. Construct optimistic transaction
      const tempId = `temp-tx-${Date.now()}`;
      const optimisticTx: Transaction = {
        id: tempId,
        workspace_id: 'local',
        account_id: newTxInput.account_id,
        destination_account_id: newTxInput.destination_account_id ?? null,
        category_id: newTxInput.category_id ?? null,
        amount_minor: newTxInput.amount_minor,
        currency: newTxInput.currency || 'RUB',
        type: newTxInput.type,
        description: newTxInput.description,
        transaction_date:
          newTxInput.transaction_date || new Date().toISOString(),
        is_cleared: newTxInput.is_cleared ?? true,
        version: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };

      // 4. Optimistically update transactions lists
      queryClient.setQueriesData<InfiniteData<PaginatedResponse<Transaction>>>(
        { queryKey: queryKeys.finance.all },
        (oldData) => {
          if (!oldData || !oldData.pages || oldData.pages.length === 0) {
            return {
              pageParams: [null],
              pages: [
                {
                  items: [optimisticTx],
                  pagination: { has_more: false, next_cursor: null },
                },
              ],
            };
          }

          const first = oldData.pages[0];
          return {
            ...oldData,
            pages: [
              {
                ...first,
                items: [optimisticTx, ...first.items],
              },
              ...oldData.pages.slice(1),
            ],
          };
        }
      );

      // 5. Optimistically adjust account balance
      if (previousAccounts) {
        queryClient.setQueryData<Account[]>(
          queryKeys.finance.accounts(),
          previousAccounts.map((acc) => {
            if (acc.id === newTxInput.account_id) {
              const delta =
                newTxInput.type === TransactionType.EXPENSE
                  ? -newTxInput.amount_minor
                  : newTxInput.type === TransactionType.INCOME
                  ? newTxInput.amount_minor
                  : -newTxInput.amount_minor; // source of transfer
              return { ...acc, balance_minor: acc.balance_minor + delta };
            }
            if (
              newTxInput.type === TransactionType.TRANSFER &&
              acc.id === newTxInput.destination_account_id
            ) {
              return {
                ...acc,
                balance_minor: acc.balance_minor + newTxInput.amount_minor,
              };
            }
            return acc;
          })
        );
      }

      return { previousAccounts, previousTransactions };
    },
    onError: (_err, _newTx, context) => {
      // Rollback to prior snapshot
      if (context?.previousAccounts) {
        queryClient.setQueryData(
          queryKeys.finance.accounts(),
          context.previousAccounts
        );
      }
      context?.previousTransactions?.forEach(([key, oldData]) => {
        queryClient.setQueryData(key, oldData);
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.finance.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
    },
  });
}

/**
 * Hook to retrieve spending budget targets and current progress for a given month.
 *
 * @param month Target month in YYYY-MM format (defaults to current month if omitted).
 */
export function useBudgets(month?: string) {
  const currentMonth = month || new Date().toISOString().substring(0, 7);

  const query = useQuery<Budget[], Error>({
    queryKey: queryKeys.finance.budgets(currentMonth),
    queryFn: () =>
      apiRequest<Budget[]>('GET', '/finance/budgets', {
        params: { month: currentMonth },
      }),
  });

  return {
    budgets: query.data ?? [],
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}

/**
 * Hook to retrieve the aggregate dashboard summary for the Today (/today) view.
 * Combines today's agenda, prioritized tasks, open time windows, and spending snapshot.
 */
export function useDashboardToday() {
  const query = useQuery<DashboardToday, Error>({
    queryKey: queryKeys.dashboard.today(),
    queryFn: () => apiRequest<DashboardToday>('GET', '/dashboard/today'),
  });

  return {
    agenda: query.data?.agenda ?? [],
    tasks: query.data?.tasks ?? [],
    free_windows: query.data?.free_windows ?? [],
    budget_summary: query.data?.budget_summary ?? {
      daily_spent_minor: 0,
      monthly_spent_minor: 0,
      monthly_limit_minor: 0,
      currency: 'RUB',
    },
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
