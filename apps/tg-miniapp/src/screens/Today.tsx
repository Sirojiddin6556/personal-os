import { TaskRow } from '../components/TaskRow';
import { ErrorBox, IconSpark, Skeleton, useToast } from '../components/ui';
import { dayTitle, greeting, hours, isSameDay, plural, time } from '../lib/format';
import { useBrief, useCreatePlan, useTasks, useToday, useToggleHabit } from '../lib/queries';
import { haptic } from '../lib/telegram';
import type { AIPlan, Task } from '../lib/types';

export function todayTasks(tasks: Task[], now = new Date()): Task[] {
  return tasks.filter((t) => {
    if (t.status === 'cancelled' || t.status === 'archived') return false;
    if (t.status === 'done') return !!t.completed_at && isSameDay(new Date(t.completed_at), now);
    if (!t.due_at) return false;
    const d = new Date(t.due_at);
    return isSameDay(d, now) || d < now;
  });
}

const PRIORITY_RANK = { critical: 0, high: 1, medium: 2, low: 3 } as const;
export function sortTasks(list: Task[]): Task[] {
  return [...list].sort(
    (a, b) =>
      Number(a.status === 'done') - Number(b.status === 'done') ||
      (PRIORITY_RANK[a.priority] ?? 2) - (PRIORITY_RANK[b.priority] ?? 2) ||
      (a.due_at ?? '9').localeCompare(b.due_at ?? '9'),
  );
}

interface Props {
  name: string;
  onOpenTask: (t: Task) => void;
  onPlan: (plan: AIPlan) => void;
  onAllTasks: () => void;
}

export function TodayScreen({ name, onOpenTask, onPlan, onAllTasks }: Props) {
  const today = useToday();
  const tasks = useTasks();
  const brief = useBrief();
  const createPlan = useCreatePlan();
  const toggleHabit = useToggleHabit();
  const toast = useToast();

  const list = sortTasks(todayTasks(tasks.data ?? []));
  const done = list.filter((t) => t.status === 'done').length;
  const pct = list.length ? Math.round((done / list.length) * 100) : 0;
  const circ = 2 * Math.PI * 32;
  const d = today.data;
  const freeHours = d?.stats?.free_hours ?? (d ? d.free_windows.reduce((a, w) => a + w.duration_minutes, 0) / 60 : 0);
  const left = list.length - done;
  const overdue = d?.overdue_count ?? 0;

  const localBrief =
    `Осталось ${left} ${plural(left, 'задача', 'задачи', 'задач')}` +
    (overdue ? `, просрочено: ${overdue}` : '') +
    `. ${d?.events.length ?? 0} ${plural(d?.events.length ?? 0, 'встреча', 'встречи', 'встреч')}, свободно ${hours(freeHours)}.`;

  const schedule = d
    ? [
        ...d.events.map((e) => ({ key: e.id, start: e.starts_at, title: e.title, meta: `${time(e.starts_at)}–${time(e.ends_at)}${e.location ? ` · ${e.location}` : ''}`, free: false })),
        ...d.free_windows.map((w) => ({ key: w.start, start: w.start, title: 'Свободное окно', meta: hours(w.duration_minutes / 60), free: true })),
      ].sort((a, b) => a.start.localeCompare(b.start))
    : [];

  const planDay = () => {
    haptic.tap();
    createPlan.mutate(undefined, {
      onSuccess: (plan) => (plan.changes.length ? onPlan(plan) : toast('AI не нашёл, что улучшить в расписании')),
      onError: (e) => toast(e instanceof Error ? e.message : 'AI недоступен', 'error'),
    });
  };

  return (
    <>
      <section className="card pad" style={{ display: 'flex', gap: 16, alignItems: 'center' }}>
        <div className="ring-wrap">
          <svg width="76" height="76" viewBox="0 0 76 76" aria-hidden="true">
            <circle cx="38" cy="38" r="32" fill="none" stroke="var(--bg2)" strokeWidth="8" />
            <circle cx="38" cy="38" r="32" fill="none" stroke="var(--accent)" strokeWidth="8" strokeLinecap="round"
              strokeDasharray={`${(circ * pct) / 100} ${circ}`} transform="rotate(-90 38 38)" />
          </svg>
          <div className="ring-label">{pct}%</div>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="small muted">{dayTitle()}</div>
          <div style={{ fontSize: 21, fontWeight: 700, marginTop: 2 }}>{greeting()}, {name}</div>
          <div className="small muted" style={{ marginTop: 4 }}>
            {done} из {list.length} задач · свободно {hours(freeHours)}
          </div>
        </div>
      </section>

      <section className="card pad soft" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: 14, color: 'var(--link)' }}>
          <IconSpark size={18} /> Утренний брифинг
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.45 }}>{brief.data?.summary || localBrief}</div>
        {brief.data?.recommendations?.slice(0, 2).map((r) => (
          <div key={r} className="small muted">• {r}</div>
        ))}
        <button type="button" className="btn small" style={{ alignSelf: 'flex-start' }} onClick={planDay} disabled={createPlan.isPending}>
          {createPlan.isPending ? 'AI думает…' : 'Спланировать день с AI'}
        </button>
      </section>

      {today.isError && <ErrorBox error={today.error} onRetry={() => today.refetch()} />}

      {today.isPending ? (
        <Skeleton h={200} />
      ) : (
        d && (
          <section className="card">
            <div className="card-title">Расписание</div>
            {schedule.length === 0 && <div className="empty">На сегодня событий нет</div>}
            {schedule.map((s) => (
              <div key={s.key} className="list-item">
                <div className="sched-time">{time(s.start)}</div>
                <div className="sched-bar" style={{ background: s.free ? 'var(--line)' : '#0ea5e9' }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14, fontWeight: 500, color: s.free ? 'var(--hint)' : undefined }}>{s.title}</div>
                  <div className="xsmall muted">{s.meta}</div>
                </div>
              </div>
            ))}
          </section>
        )
      )}

      <section className="card">
        <div className="row-between">
          <div className="card-title">Главное на сегодня</div>
          <button type="button" className="link-btn" onClick={onAllTasks}>Все задачи</button>
        </div>
        {tasks.isPending && <Skeleton h={100} />}
        {tasks.isError && <ErrorBox error={tasks.error} onRetry={() => tasks.refetch()} />}
        {tasks.isSuccess && list.length === 0 && <div className="empty">На сегодня задач нет. Нажмите «+», чтобы добавить.</div>}
        {list.slice(0, 5).map((t) => (
          <TaskRow key={t.id} task={t} onOpen={onOpenTask} />
        ))}
      </section>

      {d && d.habits.length > 0 && (
        <section className="card pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ fontWeight: 600 }}>Привычки</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {d.habits.map((h) => (
              <button
                key={h.id}
                type="button"
                className="chip habit"
                aria-pressed={h.completed_today}
                disabled={toggleHabit.isPending}
                onClick={() => {
                  haptic.select();
                  toggleHabit.mutate(h.id, { onError: (e) => toast(e instanceof Error ? e.message : 'Ошибка', 'error') });
                }}
              >
                {h.completed_today ? '✓ ' : ''}{h.title}
              </button>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
