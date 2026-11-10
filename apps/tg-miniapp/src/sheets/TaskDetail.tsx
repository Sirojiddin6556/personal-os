import { isOverdue, PRIORITY_COLOR, PRIORITY_NAME } from '../components/TaskRow';
import { Sheet, useToast } from '../components/ui';
import { dueLabel } from '../lib/format';
import { useTasks, useToggleTask, useUpdateTask } from '../lib/queries';
import { haptic } from '../lib/telegram';
import type { Priority, TaskStatus } from '../lib/types';

const STATUS_NAME: Record<TaskStatus, string> = {
  inbox: 'Входящие',
  todo: 'К выполнению',
  scheduled: 'Запланировано',
  in_progress: 'В работе',
  waiting: 'Ожидание',
  done: 'Выполнено',
  cancelled: 'Отменено',
  archived: 'В архиве',
};
const PRIORITIES: Priority[] = ['critical', 'high', 'medium', 'low'];

export function TaskDetailSheet({ taskId, onClose }: { taskId: string; onClose: () => void }) {
  const tasks = useTasks();
  const update = useUpdateTask();
  const toggle = useToggleTask();
  const toast = useToast();
  // Always read the freshest copy so the ETag version is current.
  const task = tasks.data?.find((t) => t.id === taskId);
  if (!task) return null;

  const done = task.status === 'done';
  const onError = (e: unknown) => toast(e instanceof Error ? e.message : 'Ошибка', 'error');

  const postpone = () => {
    const d = new Date();
    d.setDate(d.getDate() + 1);
    const prev = task.due_at ? new Date(task.due_at) : null;
    d.setHours(prev?.getHours() ?? 18, prev?.getMinutes() ?? 0, 0, 0);
    update.mutate(
      { task, patch: { due_at: d.toISOString(), status: task.status === 'inbox' ? 'todo' : task.status } },
      { onSuccess: () => { toast(`Перенесено на завтра: ${task.title}`); onClose(); }, onError },
    );
  };

  return (
    <Sheet label="Задача" onClose={onClose}>
      <div>
        <div className="xsmall muted">{STATUS_NAME[task.status] ?? task.status}</div>
        <h2 className="sheet-title" style={{ marginTop: 2, textDecoration: done ? 'line-through' : undefined }}>{task.title}</h2>
        {task.description && <p className="small muted" style={{ margin: '6px 0 0', whiteSpace: 'pre-wrap' }}>{task.description}</p>}
      </div>
      <div className="kv">
        <div>
          <span className="muted">Срок</span>
          <span style={{ fontWeight: 500, color: isOverdue(task) ? 'var(--bad)' : undefined }}>
            {task.due_at ? dueLabel(task.due_at) : 'Без срока'}
          </span>
        </div>
        <div>
          <span className="muted">Оценка</span>
          <span style={{ fontWeight: 500 }}>{task.estimate_minutes ? `${task.estimate_minutes} мин` : '—'}</span>
        </div>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div className="small muted" id="prio-label">Приоритет</div>
        <div className="prio-grid" role="group" aria-labelledby="prio-label">
          {PRIORITIES.map((p) => (
            <button
              key={p}
              type="button"
              aria-pressed={task.priority === p}
              disabled={update.isPending}
              onClick={() => {
                if (task.priority === p) return;
                haptic.select();
                update.mutate({ task, patch: { priority: p } }, { onError });
              }}
            >
              <span className="dot" style={{ background: PRIORITY_COLOR[p] }} />
              {PRIORITY_NAME[p]}
            </button>
          ))}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        {!done && (
          <button type="button" className="btn ghost" style={{ flex: 1 }} disabled={update.isPending} onClick={postpone}>
            На завтра
          </button>
        )}
        <button
          type="button"
          className={`btn ${done ? 'ghost' : 'okc'}`}
          style={{ flex: 1 }}
          disabled={toggle.isPending}
          onClick={() =>
            toggle.mutate(task, {
              onSuccess: () => { if (!done) toast(`Готово: ${task.title}`); onClose(); },
              onError,
            })
          }
        >
          {done ? 'Вернуть в работу' : 'Выполнить'}
        </button>
      </div>
    </Sheet>
  );
}
