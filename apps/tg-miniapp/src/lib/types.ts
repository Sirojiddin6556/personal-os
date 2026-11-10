/** Subset of FastAPI response models used by the Mini App. */

export type Priority = 'low' | 'medium' | 'high' | 'critical';
export type TaskStatus =
  | 'inbox'
  | 'todo'
  | 'scheduled'
  | 'in_progress'
  | 'waiting'
  | 'done'
  | 'cancelled'
  | 'archived';

export interface Task {
  id: string;
  title: string;
  description?: string | null;
  status: TaskStatus;
  priority: Priority;
  due_at?: string | null;
  completed_at?: string | null;
  project_id?: string | null;
  estimate_minutes?: number | null;
  version: number;
}

export interface CursorPage<T> {
  items: T[];
  next_cursor?: string | null;
  has_more: boolean;
}

export interface CalendarEvent {
  id: string;
  title: string;
  starts_at: string;
  ends_at: string;
  is_all_day: boolean;
  location?: string | null;
}

export interface TimeWindow {
  start: string;
  end: string;
  duration_minutes: number;
}

export interface HabitSummary {
  id: string;
  title: string;
  current_streak: number;
  best_streak: number;
  completed_today: boolean;
}

export interface DashboardToday {
  events: CalendarEvent[];
  top_tasks: Task[];
  overdue_tasks: Task[];
  overdue_count: number;
  free_windows: TimeWindow[];
  budget_summary: {
    total_balance_minor: number;
    today_spent_minor: number;
    monthly_spent_minor: number;
    monthly_limit_minor: number;
    currency: string;
    active_accounts_count: number;
  };
  habits: HabitSummary[];
  stats?: {
    total_tasks: number;
    completed_tasks: number;
    overdue_count: number;
    events_count: number;
    free_hours: number;
  } | null;
}

export interface MorningBrief {
  date: string;
  summary: string;
  recommendations: string[];
}

export interface AIPlan {
  plan_id: string;
  status: string;
  changes: Array<Record<string, unknown>>;
  ai_explanation: string;
}

export interface Account {
  id: string;
  name: string;
  type: string;
  currency: string;
  current_balance_minor: number;
  is_archived: boolean;
}

export interface Category {
  id: string;
  name: string;
  color: string;
  type: string;
}

export interface Transaction {
  id: string;
  account_id: string;
  account_name?: string | null;
  category_id?: string | null;
  category_name?: string | null;
  category?: string | null;
  amount_minor: number;
  currency: string;
  type: string;
  transaction_type?: string | null;
  status: string;
  note?: string | null;
  description?: string | null;
  occurred_at: string;
}

export interface Habit {
  id: string;
  title: string;
  current_streak: number;
  best_streak: number;
  is_completed_today: boolean;
}

export interface Reminder {
  id: string;
  title: string;
  remind_at: string;
  is_dismissed: boolean;
}

export interface Journal {
  entry_date: string;
  evening_reflection?: string | null;
  notes?: string | null;
}

export interface TelegramAuthResponse {
  access_token: string;
  expires_in: number;
  workspace_id: string;
  user: { id: string; full_name: string; timezone: string };
  telegram_user: { id: number; first_name?: string | null; username?: string | null };
}
