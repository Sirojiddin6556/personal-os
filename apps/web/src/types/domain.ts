/**
 * @file domain.ts
 * @description Core domain entity types, enums, and API transfer schemas for Personal OS.
 * Aligned with Solution Architecture (04), System Analyst (06), and UI Kit (18).
 */

// ============================================================================
// ENUMS & VALUE OBJECTS
// ============================================================================

/**
 * Task lifecycle status in the Kanban state machine.
 */
export enum TaskStatus {
  INBOX = 'inbox',
  TODO = 'todo',
  BACKLOG = 'backlog',
  SCHEDULED = 'scheduled',
  IN_PROGRESS = 'in_progress',
  WAITING = 'waiting',
  BLOCKED = 'blocked',
  DONE = 'done',
  CANCELED = 'canceled',
}

export type TaskStatusType =
  | 'inbox'
  | 'todo'
  | 'backlog'
  | 'scheduled'
  | 'in_progress'
  | 'waiting'
  | 'blocked'
  | 'done'
  | 'canceled';

/**
 * Task priority tiers aligned with Eisenhower Matrix principles.
 * P1: Urgent / Critical
 * P2: High
 * P3: Medium / Normal
 * P4: Low / Someday
 */
export enum Priority {
  P1 = 'p1',
  P2 = 'p2',
  P3 = 'p3',
  P4 = 'p4',
}

export type TaskPriority =
  | 'critical'
  | 'urgent'
  | 'high'
  | 'medium'
  | 'low'
  | 'p1'
  | 'p2'
  | 'p3'
  | 'p4'
  | Priority;

export type PriorityType = TaskPriority;

/**
 * Financial ledger transaction classification.
 */
export enum TransactionType {
  INCOME = 'income',
  EXPENSE = 'expense',
  TRANSFER = 'transfer',
}

export type TransactionTypeValue = 'income' | 'expense' | 'transfer';


/**
 * Financial account category.
 */
export type AccountType = 'checking' | 'savings' | 'credit' | 'cash' | 'crypto' | 'investment';

/**
 * Calendar event synchronization source.
 */
export type CalendarProvider = 'google' | 'apple' | 'outlook' | 'internal';

/**
 * Notification delivery channels.
 */
export type NotificationChannel = 'in_app' | 'push' | 'telegram';

/**
 * Risk tier for AI automated actions and plans.
 */
export type RiskTier = 'low' | 'medium' | 'high';

// ============================================================================
// DOMAIN ENTITIES
// ============================================================================

/**
 * Subtask checklist item associated with a primary task.
 */
export interface Subtask {
  /** Unique subtask identifier (UUIDv4) */
  id: string;
  /** Parent task identifier */
  task_id?: string;
  /** Subtask checklist title */
  title: string;
  /** Canonical completion flag */
  is_completed?: boolean;
  /** Convenience UI alias for is_completed */
  completed?: boolean;
  /** Relative visual position */
  sort_order?: number;
  /** Creation timestamp (ISO 8601) */
  created_at?: string;
}

/**
 * Primary work item in Personal OS with support for Kanban projections,
 * deadlines, and optimistic concurrency versioning.
 */
export interface Task {
  /** Unique task identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Short descriptive title */
  title: string;
  /** Detailed Markdown-formatted body */
  description_markdown?: string;
  /** Current state machine status */
  status: TaskStatus | TaskStatusType;
  /** Execution priority tier */
  priority: Priority | TaskPriority;
  /** Strict deadline timestamp (ISO 8601 UTC) */
  due_date?: string | null;
  /** Convenience UI alias for deadline timestamp */
  due_at?: string | null;
  /** Planned calendar allocation date (YYYY-MM-DD) */
  scheduled_date?: string | null;
  /** Parent project identifier */
  project_id?: string | null;
  /** Populated parent project metadata for UI cards */
  project?: {
    id: string;
    name: string;
    color: string;
  } | null;
  /** Organizational tag labels */
  tags?: string[];
  /** Kanban column sort order */
  sort_order?: number;
  /** Estimated time in minutes */
  estimated_duration_minutes?: number | null;
  /** Actual spent time in minutes */
  actual_duration_minutes?: number | null;
  /** Completion timestamp (ISO 8601 UTC) */
  completed_at?: string | null;
  /** Subtask checklist items */
  subtasks?: Subtask[];
  /** Monotonically increasing version counter for optimistic locking (If-Match) */
  version?: number;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at: string;
  /** Last update timestamp (ISO 8601 UTC) */
  updated_at: string;
}

/**
 * Strategic goal or high-level grouping of tasks and milestones.
 */
export interface Project {
  /** Unique project identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id: string;
  /** Project display name */
  name: string;
  /** Project description / goals */
  description?: string;
  /** Color code for badges and calendar highlights (Hex/HSL) */
  color: string;
  /** Target completion deadline */
  target_date?: string | null;
  /** Project lifecycle state */
  status: 'active' | 'paused' | 'completed' | 'archived';
  /** Computed completion percentage (0-100) */
  progress_percent: number;
  /** Dedicated financial budget limit in minor units (e.g. cents) */
  budget_limit_minor?: number | null;
  /** Currency code (e.g. RUB, USD) */
  currency?: string;
  /** Optimistic concurrency version */
  version?: number;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at: string;
  /** Last update timestamp (ISO 8601 UTC) */
  updated_at: string;
}

/**
 * Calendar event or meeting slot.
 */
export interface CalendarEvent {
  /** Unique event identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Event title / summary */
  title: string;
  /** Event description notes */
  description?: string;
  /** Start datetime in ISO 8601 UTC */
  start_time: string;
  /** End datetime in ISO 8601 UTC */
  end_time: string;
  /** Convenience UI alias for start */
  start?: string;
  /** Convenience UI alias for end */
  end?: string;
  /** Convenience color code */
  color?: string;
  /** Full day event flag */
  is_all_day?: boolean;

  /** Whether the event was imported from external provider */
  is_external?: boolean;
  /** External calendar integration provider name */
  external_provider?: CalendarProvider | null;
  /** Foreign event identifier from external provider */
  external_event_id?: string | null;
  /** Recurrence rule (RFC 5545 RRULE string) */
  rrule?: string | null;
  /** Physical or virtual meeting location URL */
  location?: string | null;
  /** Associated task ID if event is a time-box */
  task_id?: string | null;
  /** Optimistic concurrency version */
  version?: number;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
  /** Last update timestamp (ISO 8601 UTC) */
  updated_at?: string;
}

/**
 * Scheduled dedicated block of focused time for a specific task.
 */
export interface TimeBlock {
  /** Unique timeblock identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Associated task reference */
  task_id: string;
  /** Block start time in ISO 8601 UTC */
  start_time: string;
  /** Block end time in ISO 8601 UTC */
  end_time: string;
  /** If true, AI auto-rescheduler will not move this block */
  is_locked?: boolean;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
  /** Last update timestamp (ISO 8601 UTC) */
  updated_at?: string;
}

/**
 * Bank, cash, or crypto account holding monetary balance.
 */
export interface Account {
  /** Unique account identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Account title (e.g. "Tinkoff Black", "Cash Wallet") */
  name: string;
  /** Account category */
  type: AccountType;
  /** Current balance in minor units (integer: cents / kopecks) */
  balance_minor: number;
  /** 3-letter currency code (ISO 4217) */
  currency: string;
  /** Whether the account is hidden from active pickers */
  is_archived?: boolean;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
  /** Last update timestamp (ISO 8601 UTC) */
  updated_at?: string;
}

/**
 * Category for grouping transactions and setting budget limits.
 */
export interface Category {
  /** Unique category identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Category display name */
  name: string;
  /** Lucide icon identifier */
  icon?: string;
  /** Visual badge color */
  color?: string;
  /** Parent category ID for nested subcategories */
  parent_id?: string | null;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
}

/**
 * Immutable financial transaction entry in the ledger.
 */
export interface Transaction {
  /** Unique transaction identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Source financial account ID */
  account_id: string;
  /** Source financial account name for UI displays */
  account_name?: string;
  /** Destination account ID for transfer transactions */
  destination_account_id?: string | null;
  /** Category reference ID */
  category_id?: string | null;
  /** Display category name */
  category?: string | null;
  /** Display category icon */
  category_icon?: string;

  /** Amount in integer minor units (always positive integer) */
  amount_minor: number;
  /** Convenience display amount in major units (e.g. 150.50) */
  amount?: number;
  /** Currency code (ISO 4217) */
  currency: string;
  /** Ledger type */
  type: TransactionType | TransactionTypeValue;
  /** Transaction note / description */
  description: string;
  /** Transaction occurrence date (ISO 8601 or YYYY-MM-DD) */
  transaction_date: string;
  /** Convenience UI alias for transaction_date */
  date?: string;
  /** Reconciliation status with bank statement */
  is_cleared?: boolean;
  /** Optimistic concurrency version */
  version?: number;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
  /** Last update timestamp (ISO 8601 UTC) */
  updated_at?: string;
}

/**
 * Category spending limit allocated for a specific calendar month.
 */
export interface Budget {
  /** Unique budget identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Target category */
  category_id: string;
  /** Budget month in YYYY-MM format */
  month: string;
  /** Max limit in minor units */
  limit_minor: number;
  /** Current accumulated spend in minor units */
  current_spent_minor: number;
  /** Currency code (ISO 4217) */
  currency: string;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
  /** Last update timestamp (ISO 8601 UTC) */
  updated_at?: string;
}

/**
 * Knowledge base note with Markdown content and semantic embeddings.
 */
export interface Note {
  /** Unique note identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Note headline */
  title: string;
  /** Markdown body content */
  content_markdown: string;
  /** Folder categorization */
  folder_id?: string | null;
  /** Searchable semantic tags */
  tags?: string[];
  /** Pinned to top of list */
  is_pinned?: boolean;
  /** Archived flag */
  is_archived?: boolean;
  /** Concurrency version */
  version?: number;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
  /** Last update timestamp (ISO 8601 UTC) */
  updated_at?: string;
}

/**
 * Habit entity for tracking daily/weekly consistency.
 */
export interface Habit {
  /** Unique habit identifier (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Habit title (e.g. "Drink 2L Water", "Morning Run") */
  title: string;
  /** Habit instructions or notes */
  description?: string;
  /** Target frequency */
  frequency: 'daily' | 'weekly';
  /** Required completions per week */
  target_days_per_week: number;
  /** Current continuous streak in days */
  current_streak_days: number;
  /** Longest all-time streak in days */
  longest_streak_days: number;
  /** Last check-in date (YYYY-MM-DD) */
  last_logged_date?: string | null;
  /** Archived status */
  is_archived?: boolean;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
  /** Last update timestamp (ISO 8601 UTC) */
  updated_at?: string;
}

/**
 * Habit check-in log entry.
 */
export interface HabitLog {
  /** Unique log ID (UUIDv4) */
  id: string;
  /** Parent habit ID */
  habit_id: string;
  /** Date of log (YYYY-MM-DD) */
  log_date: string;
  /** Value (1 for boolean check, or numeric count) */
  value: number;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
}

/**
 * In-app or push notification record.
 */
export interface Notification {
  /** Unique notification ID (UUIDv4) */
  id: string;
  /** Tenant isolation identifier */
  workspace_id?: string;
  /** Alert headline */
  title: string;
  /** Descriptive body */
  message?: string;
  body?: string;
  /** Channel through which alert was routed */
  channel: NotificationChannel | string;
  /** Urgency level */
  priority: 'low' | 'normal' | 'high' | 'urgent' | string;
  /** Read acknowledgement flag */
  is_read?: boolean;
  status?: string;
  /** Timestamp when user marked as read */
  read_at?: string | null;
  /** Optional deep link URI */
  link_url?: string | null;
  /** Creation timestamp (ISO 8601 UTC) */
  created_at?: string;
  /** Update timestamp (ISO 8601 UTC) */
  updated_at?: string;
}

// ============================================================================
// AI ADVISOR & PLANNING SCHEMAS
// ============================================================================

/**
 * Individual atomic operation inside an AI-proposed execution plan.
 */
export interface AIPlanChange {
  /** Target domain entity type */
  entity_type: 'task' | 'calendar_event' | 'timeblock' | 'transaction' | 'note' | string;
  /** Action verb */
  action: 'create' | 'update' | 'delete';
  /** Target entity ID if updating or deleting */
  entity_id?: string;
  /** Human-readable explanation of why this change is suggested */
  description: string;
  /** State before change (for diff preview) */
  before?: Record<string, unknown> | null;
  /** Proposed new state (for diff preview) */
  after?: Record<string, unknown> | null;
  /** Safety risk assessment tier */
  risk_tier: RiskTier;
}

/**
 * AI-generated execution proposal requiring user review (Human-in-the-Loop).
 */
export interface AIPreviewPlan {
  /** Unique plan execution ID */
  plan_id: string;
  /** Initial prompt or trigger that provoked this plan */
  prompt: string;
  /** High-level summary of proposed changes */
  summary: string;
  /** List of atomic operations */
  changes: AIPlanChange[];
  /** Whether user must explicitly click Apply */
  requires_confirmation: boolean;
  /** Plan execution status */
  status: 'draft' | 'applied' | 'rejected';
  /** Timestamp when plan was prepared */
  created_at: string;
}

/**
 * Result of natural language intent parsing (NLP / Quick Add).
 */
export interface ParsedIntent {
  /** Detected target domain action */
  intent: 'create_task' | 'create_event' | 'create_transaction' | 'create_note';
  /** Extracted structured fields (title, date, amount, priority, tags) */
  fields: Record<string, unknown>;
  /** Model confidence score (0.0 - 1.0) */
  confidence: number;
}

// ============================================================================
// COMPOSITE DASHBOARD SCHEMAS
// ============================================================================

/**
 * Open time slot on calendar suitable for deep work or tasks.
 */
export interface FreeWindow {
  /** Start time (ISO 8601 UTC) */
  start_time: string;
  /** End time (ISO 8601 UTC) */
  end_time: string;
  /** Duration in minutes */
  duration_minutes: number;
}

/**
 * Aggregated summary of today's financial spending.
 */
export interface BudgetSummary {
  /** Money spent today in minor units */
  daily_spent_minor: number;
  /** Total money spent this calendar month in minor units */
  monthly_spent_minor: number;
  /** Monthly total budget limit in minor units */
  monthly_limit_minor: number;
  /** Base currency code */
  currency: string;
  /** Convenience display spent */
  spent?: number;
  /** Convenience display limit */
  limit?: number;
  /** Convenience display percentage */
  percentage?: number;
  /** Convenience display remaining */
  remaining?: number;
  /** Category if specific */
  category?: string;
}


/**
 * Aggregate payload for the Today Dashboard screen (/today).
 */
export interface DashboardToday {
  /** Calendar schedule for the current day */
  agenda: CalendarEvent[];
  /** Tasks due today or active in progress */
  tasks: Task[];
  /** Available unallocated time slots */
  free_windows: FreeWindow[];
  /** Financial expenditure snapshot */
  budget_summary: BudgetSummary;
}

// ============================================================================
// API PAGINATION & METADATA SCHEMAS
// ============================================================================

/**
 * Cursor-based pagination metadata.
 */
export interface PaginationMeta {
  /** Whether additional records exist past this page */
  has_more: boolean;
  /** Cursor token to pass into next request */
  next_cursor: string | null;
  /** Approximate total record count if available */
  total_count_approx?: number;
}

/**
 * Generic cursor-paginated list wrapper from Core REST API.
 */
export interface PaginatedResponse<TItem> {
  /** List of records */
  items: TItem[];
  /** Pagination traversal tokens */
  pagination: PaginationMeta;
}

// ============================================================================
// KNOWLEDGE & NOTES DOMAIN
// ============================================================================

export interface NoteCreateInput {
  title: string;
  content_markdown?: string;
  is_pinned?: boolean;
}

export interface NoteUpdateInput {
  title?: string;
  content_markdown?: string;
  is_pinned?: boolean;
  is_archived?: boolean;
}

export interface NoteSearchResult {
  note_id: string;
  title: string;
  snippet: string;
  score: number;
}

// ============================================================================
// NOTIFICATIONS DOMAIN
// ============================================================================

export interface NotificationCreateInput {
  user_id: string;
  title: string;
  body: string;
  channel?: string;
  priority?: string;
}

export interface UnreadCountResponse {
  unread_count: number;
}

// ============================================================================
// INTEGRATIONS DOMAIN
// ============================================================================

export interface IntegrationStatus {
  provider: 'google_calendar' | 'telegram' | string;
  status: 'connected' | 'disconnected' | 'syncing' | 'error';
  last_sync: string | null;
  error_message?: string | null;
  metadata?: Record<string, unknown>;
}

