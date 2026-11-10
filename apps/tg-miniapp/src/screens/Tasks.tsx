import { useState } from 'react';
import { isOverdue, TaskRow } from '../components/TaskRow';
import { ErrorBox, Skeleton } from '../components/ui';
import { useTasks } from '../lib/queries';
import { haptic } from '../lib/telegram';
import type { Task } from '../lib/types';
import { sortTasks, todayTasks } from './Today';

type Filter = 'today' | 'inbox' | 'all';
const FILTERS: Array<[Filter, string]> = [
  ['today', 'Сегодня'],
  ['inbox', 'Входящие'],
  ['all', 'Все'],
];

const active = (t: Task) => !['done', 'cancelled', 'archived'].includes(t.status);

export function TasksScreen({ onOpenTask }: { onOpenTask: (t: Task) => void }) {
  const [filter, setFilter] = useState<Filter>('today');
  const tasks = useTasks();
  const all = tasks.data ?? [];

  const lists: Record<Filter, Task[]> = {
    today: todayTasks(all),
    inbox: all.filter((t) => t.status === 'inbox'),
    all: all.filter(active),
  };
  const list = sortTasks(lists[filter]);
  const overdue = all.filter((t) => isOverdue(t)).length;

  return (
    <>
      <div className="row-between" style={{ padding: '0 4px' }}>
        <h1 className="h1" style={{ padding: 0 }}>Задачи</h1>
        {overdue > 0 && (
          <span className="xsmall" style={{ fontWeight: 600, color: 'var(--bad)', background: 'var(--badsoft)', borderRadius: 8, padding: '4px 8px' }}>
            Просрочено: {overdue}
          </span>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8 }} role="group" aria-label="Фильтр">
        {FILTERS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className="chip"
            aria-pressed={filter === id}
            onClick={() => {
              haptic.select();
              setFilter(id);
            }}
          >
            {label} <span style={{ opacity: 0.7 }}>{lists[id].filter(active).length}</span>
          </button>
        ))}
      </div>

      <section className="card" style={{ padding: '0 14px' }}>
        {tasks.isPending && <Skeleton h={180} />}
        {tasks.isError && <ErrorBox error={tasks.error} onRetry={() => tasks.refetch()} />}
        {tasks.isSuccess && list.length === 0 && <div className="empty">Здесь пусто. Нажмите «+», чтобы добавить.</div>}
        {list.map((t) => (
          <TaskRow key={t.id} task={t} onOpen={onOpenTask} chevron />
        ))}
      </section>
    </>
  );
}
