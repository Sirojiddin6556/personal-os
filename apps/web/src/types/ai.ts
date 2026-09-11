import { TaskPriority } from './domain';

export type AIChangeType = 'reschedule' | 'create' | 'update' | 'delete';

export interface AIPreviewChange {
  id: string;
  title: string;
  type: AIChangeType;
  before?: string;
  after?: string;
  conflict_resolved?: boolean;
}

export interface AIPreviewPlan {
  id: string;
  title: string;
  description?: string;
  confidence: number; // e.g. 94 or 0.94
  changes: AIPreviewChange[];
  created_at: string;
}

export interface ProposedScheduleBlock {
  id: string;
  title: string;
  time: string;
  type: string;
}

export interface MorningBrief {
  id: string;
  date: string;
  stats: {
    events_count: number;
    tasks_count: number;
    free_hours: number;
    critical_tasks_count?: number;
  };
  proposed_schedule: ProposedScheduleBlock[];
  ai_comment: string;
}

export interface ParsedQuickAdd {
  intent: 'task' | 'event' | 'expense' | 'note';
  title: string;
  due_date?: string;
  priority?: TaskPriority;
  project?: string;
  amount?: number;
  currency?: string;
  account?: string;
  category?: string;
  time?: string;
  confidence: number;
}

