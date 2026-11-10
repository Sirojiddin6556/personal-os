import { dueLabel } from '../lib/format';
import { haptic } from '../lib/telegram';
import { useToggleTask } from '../lib/queries';
import type { Priority, Task } from '../lib/types';
import { IconCheck, IconChevron, useToast } from './ui';

export const PRIORITY_COLOR: Record<Priority, string> = {
  critical: 'var(--p-critical)',
  high: 'var(--p-high)',
  medium: 'var(--p-medium)',
  low: 'var(--p-low)',
};
export const PRIORITY_NAME: Record<Priority, string> = {
  critical: 'Срочно',
  high: 'Высокий',
  medium: 'Средний',
  low: 'Низкий',
};

export function isOverdue(t: Task, now = new Date()): boolean {
  return !!t.due_at && t.status !== 'done' && new Date(t.due_at) < now;
}

export function TaskRow({ task, onOpen, chevron }: { task: Task; onOpen: (t: Task) => void; chevron?: boolean }) {
  const toggle = useToggleTask();
  const toast = useToast();
  const done = task.status === 'done';
  const overdue = isOverdue(task);
  const meta = [task.status === 'inbox' ? 'Входящие' : null, dueLabel(task.due_at)].filter(Boolean).join(' · ');

  const onToggle = () => {
    haptic.tap();
    toggle.mutate(task, {
      onSuccess: () => !done && toast(`Готово: ${task.title}`),
      onError: (e) => toast(e instanceof Error ? e.message : 'Ошибка', 'error'),
    });
  };

  return (
    <div className="task-row">
      <button
        type="button"
        role="checkbox"
        aria-checked={done}
        aria-label={done ? `Вернуть задачу: ${task.title}` : `Выполнить: ${task.title}`}
        className="check"
        onClick={onToggle}
      >
        <span><IconCheck size={13} stroke={3.5} /></span>
      </button>
      <button type="button" className="task-body" onClick={() => onOpen(task)} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span className={`task-title ${done ? 'done' : ''}`} style={{ display: 'block' }}>{task.title}</span>
          <span className={`task-meta ${overdue ? 'overdue' : ''}`}>
            <span className="dot" style={{ background: PRIORITY_COLOR[task.priority] ?? PRIORITY_COLOR.medium }} />
            {meta || PRIORITY_NAME[task.priority]}
          </span>
        </span>
        {chevron && <span className="muted" style={{ display: 'flex' }}><IconChevron size={16} /></span>}
      </button>
    </div>
  );
}
