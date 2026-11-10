import { useEffect, useState } from 'react';
import { ErrorBox, IconBell, Skeleton, useToast } from '../components/ui';
import { dueLabel, isoDate, plural } from '../lib/format';
import { useHabits, useJournal, useReminders, useSaveJournal, useToggleHabit } from '../lib/queries';
import { haptic } from '../lib/telegram';

export function PlannerScreen() {
  const habits = useHabits();
  const reminders = useReminders();
  const toggle = useToggleHabit();
  const toast = useToast();
  const date = isoDate();
  const journal = useJournal(date);
  const save = useSaveJournal();
  const [text, setText] = useState('');
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!dirty && journal.data) setText(journal.data.evening_reflection ?? '');
  }, [journal.data, dirty]);

  const upcoming = (reminders.data ?? [])
    .filter((r) => !r.is_dismissed)
    .sort((a, b) => a.remind_at.localeCompare(b.remind_at));

  return (
    <>
      <h1 className="h1">Ежедневник</h1>

      <section className="card">
        <div className="card-title">Привычки</div>
        {habits.isPending && <Skeleton h={120} />}
        {habits.isError && <ErrorBox error={habits.error} onRetry={() => habits.refetch()} />}
        {habits.isSuccess && habits.data.length === 0 && <div className="empty">Привычек пока нет</div>}
        {(habits.data ?? []).map((h) => {
          const streak = h.current_streak;
          return (
            <div key={h.id} className="list-item">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{h.title}</div>
                <div className="xsmall muted">
                  {streak > 0 ? `Серия: ${streak} ${plural(streak, 'день', 'дня', 'дней')}` : 'Начните серию сегодня'}
                  {h.best_streak > streak ? ` · рекорд ${h.best_streak}` : ''}
                </div>
              </div>
              <button
                type="button"
                className="chip habit"
                aria-pressed={h.is_completed_today}
                style={{ borderRadius: 10, minWidth: 104 }}
                disabled={toggle.isPending}
                onClick={() => {
                  haptic.select();
                  toggle.mutate(h.id, { onError: (e) => toast(e instanceof Error ? e.message : 'Ошибка', 'error') });
                }}
              >
                {h.is_completed_today ? 'Сделано' : 'Отметить'}
              </button>
            </div>
          );
        })}
      </section>

      <section className="card">
        <div className="card-title">Напоминания</div>
        {reminders.isPending && <Skeleton h={80} />}
        {reminders.isError && <ErrorBox error={reminders.error} onRetry={() => reminders.refetch()} />}
        {reminders.isSuccess && upcoming.length === 0 && (
          <div className="empty">Нет активных напоминаний. Напишите «напомни … в 19:00» через «+».</div>
        )}
        {upcoming.map((r) => (
          <div key={r.id} className="list-item">
            <span style={{ color: 'var(--warn)', display: 'flex' }}><IconBell size={18} /></span>
            <div style={{ flex: 1, fontSize: 14 }}>{r.title}</div>
            <div className="small muted">{dueLabel(r.remind_at)}</div>
          </div>
        ))}
      </section>

      <section className="card pad" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <label htmlFor="journal" style={{ fontWeight: 600 }}>Итог дня</label>
        <textarea
          id="journal"
          className="textarea"
          rows={4}
          placeholder="Что получилось сегодня? Что перенести на завтра?"
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setDirty(true);
          }}
        />
        <button
          type="button"
          className="btn small"
          style={{ alignSelf: 'flex-end' }}
          disabled={save.isPending || !dirty}
          onClick={() =>
            save.mutate(
              { entry_date: date, evening_reflection: text },
              {
                onSuccess: () => {
                  setDirty(false);
                  toast('Итог дня сохранён');
                },
                onError: (e) => toast(e instanceof Error ? e.message : 'Ошибка', 'error'),
              },
            )
          }
        >
          {save.isPending ? 'Сохраняю…' : 'Сохранить'}
        </button>
      </section>
    </>
  );
}
