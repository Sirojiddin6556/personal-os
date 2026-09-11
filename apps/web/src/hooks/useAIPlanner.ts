/**
 * @file useAIPlanner.ts
 * @description TanStack Query hooks for AI planning operations: generating action proposals,
 * confirming and executing multi-entity plans with Human-in-the-Loop gates, and parsing Quick Add inputs.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '@/lib/api-client';
import { queryKeys } from '@/lib/query-keys';
import { AIPreviewPlan, ParsedIntent } from '@/types/domain';

export interface CreatePlanInput {
  /** Natural language request or command for the AI assistant */
  prompt: string;
  /** User's local timezone (e.g. "Europe/Moscow", "America/New_York") */
  user_timezone?: string;
  /** Contextual data or active screen state */
  context?: Record<string, unknown>;
}

export interface ApplyPlanInput {
  /** Unique plan identifier to execute */
  plan_id: string;
  /** Optional subset of change indices if user deselected some items */
  confirmed_change_indices?: number[];
}

export interface ApplyPlanResponse {
  plan_id: string;
  status: 'applied';
  executed_changes_count: number;
  result_entity_ids: string[];
}

export interface ParseInputParams {
  /** Raw text captured from quick add bar or voice transcription */
  text: string;
  /** User's current timezone */
  user_timezone?: string;
}

/**
 * Mutation hook to request the AI Advisor to draft a multi-entity plan.
 * Returns a preview of changes (diff) requiring explicit human confirmation.
 */
export function useCreatePlan() {
  const queryClient = useQueryClient();

  return useMutation<AIPreviewPlan, Error, CreatePlanInput>({
    mutationFn: (input: CreatePlanInput) =>
      apiRequest<AIPreviewPlan, CreatePlanInput>('POST', '/advisor/plans', {
        body: input,
      }),
    onSuccess: (newPlan) => {
      queryClient.setQueryData(queryKeys.advisor.planDetail(newPlan.plan_id), newPlan);
      queryClient.invalidateQueries({ queryKey: queryKeys.advisor.plans() });
    },
  });
}

/**
 * Mutation hook to apply an AI proposal after user confirmation (Human-in-the-Loop).
 * Upon successful execution, invalidates all affected domain caches.
 */
export function useApplyPlan() {
  const queryClient = useQueryClient();

  return useMutation<ApplyPlanResponse, Error, ApplyPlanInput>({
    mutationFn: ({ plan_id, confirmed_change_indices }: ApplyPlanInput) =>
      apiRequest<ApplyPlanResponse, { confirmed_change_indices?: number[] }>(
        'POST',
        `/advisor/plans/${plan_id}/apply`,
        {
          body: { confirmed_change_indices },
        }
      ),
    onSuccess: () => {
      // Refresh all domains affected by AI plan application
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.finance.all });
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboard.today() });
      queryClient.invalidateQueries({ queryKey: queryKeys.advisor.plans() });
    },
  });
}

/**
 * Mutation hook for real-time natural language input parsing (NLP / Quick Add).
 * Resolves raw text into structured intents: task, event, expense, or note.
 */
export function useParseInput() {
  return useMutation<ParsedIntent, Error, ParseInputParams>({
    mutationFn: (params: ParseInputParams) =>
      apiRequest<ParsedIntent, ParseInputParams>('POST', '/advisor/parse', {
        body: {
          ...params,
          user_timezone:
            params.user_timezone ||
            (typeof Intl !== 'undefined' ? Intl.DateTimeFormat().resolvedOptions().timeZone : 'UTC'),
        },
      }),
  });
}
