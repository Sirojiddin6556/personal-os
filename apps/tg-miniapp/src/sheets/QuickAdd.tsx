import { useEffect, useRef, useState } from 'react';
import { Sheet, useToast } from '../components/ui';
import { dueLabel, money } from '../lib/format';
import { guessCategory, parseQuickAdd } from '../lib/parse';
import { useAccounts, useCategories, useCreateExpense, useCreateReminder, useCreateTask } from '../lib/queries';

const EXAMPLES = ['45000 такси', 'Потратил 120 тыс на обед', 'Купить молоко завтра', 'Напомни позвонить маме в 19:00'];

export function QuickAddSheet({ prefill, onClose }: { prefill: string; onClose: () => void }) {
  const [text, setText] = useState(prefill);
  const inputRef = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const accounts = useAccounts();
  const categories = useCategories();
  const createTask = useCreateTask();
  const createExpense = useCreateExpense();
  const createReminder = useCreateReminder();
  const busy = createTask.isPending || createExpense.isPending || createReminder.isPending;

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.focus();
    el.setSelectionRange(0, 0); // caret before a prefilled " такси"
  }, []);

  const p = parseQuickAdd(text);
  const account = (accounts.data ?? []).find((a) => !a.is_archived && a.type === 'cash') ?? (accounts.data ?? []).find((a) => !a.is_archived);

  let tag = 'AI';
  let tagColor = 'var(--hint)';
  let preview = 'Начните вводить текст';
  let action = 'Добавить';
  let blocked: string | null = null;
  if (p?.kind === 'expense') {
    tag = 'РАСХОД'; tagColor = 'var(--ok)'; action = 'Добавить расход';
    preview = `${money(p.amountMinor, p.currency)} · ${p.category}${account ? ` · ${account.name}` : ''}`;
    if (accounts.isSuccess && !account) blocked = 'Нет счёта для списания — создайте его в веб-версии';
  } else if (p?.kind === 'reminder') {
    tag = 'НАПОМ.'; tagColor = 'var(--warn)'; action = 'Поставить напоминание';
    preview = `${p.title} · ${dueLabel(p.remindAt.toISOString())}`;
  } else if (p?.kind === 'task') {
    tag = 'ЗАДАЧА'; tagColor = 'var(--accent)'; action = 'Создать задачу';
    preview = `${p.title} · ${p.dueAt ? dueLabel(p.dueAt.toISOString()) : 'во Входящие'}`;
  }

  const onError = (e: unknown) => toast(e instanceof Error ? e.message : 'Не удалось сохранить', 'error');

  const submit = () => {
    if (!p || busy || blocked) return;
    if (p.kind === 'expense' && account) {
      const wanted = guessCategory(p.category).toLowerCase();
      const cat = (categories.data ?? []).find((c) => c.type === 'expense' && c.name.toLowerCase() === wanted);
      createExpense.mutate(
        {
          account_id: account.id,
          amount_minor: p.amountMinor,
          currency: p.currency,
          ...(cat ? { category_id: cat.id } : { category_name: guessCategory(p.category) }),
          note: p.category,
        },
        { onSuccess: () => { toast(`Расход ${money(p.amountMinor, p.currency)} · ${p.category}`); onClose(); }, onError },
      );
    } else if (p.kind === 'reminder') {
      createReminder.mutate(
        { title: p.title, remind_at: p.remindAt.toISOString() },
        { onSuccess: () => { toast(`Напоминание: ${p.title}`); onClose(); }, onError },
      );
    } else if (p.kind === 'task') {
      createTask.mutate(
        { title: p.title, priority: p.priority, due_at: p.dueAt ? p.dueAt.toISOString() : null },
        { onSuccess: () => { toast(`Задача создана: ${p.title}`); onClose(); }, onError },
      );
    }
  };

  return (
    <Sheet label="Быстрое добавление" onClose={onClose}>
      <h2 className="sheet-title">Быстрое добавление</h2>
      <label htmlFor="qa" className="small muted">Пишите как боту — задача, расход или напоминание</label>
      <input
        id="qa"
        ref={inputRef}
        className="input"
        value={text}
        placeholder="Например: 45000 такси"
        autoComplete="off"
        enterKeyHint="done"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
      />
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {EXAMPLES.map((x) => (
          <button key={x} type="button" className="chip" style={{ height: 34, fontSize: 13, fontWeight: 400 }} onClick={() => setText(x)}>
            {x}
          </button>
        ))}
      </div>
      <div className="soft" style={{ minHeight: 56, borderRadius: 12, padding: '10px 12px', display: 'flex', gap: 10, alignItems: 'center' }} aria-live="polite">
        <span className="tag" style={{ background: tagColor }}>{tag}</span>
        <div style={{ fontSize: 14, fontWeight: 600 }}>{preview}</div>
      </div>
      {blocked && <div className="small" style={{ color: 'var(--bad)' }}>{blocked}</div>}
      <button type="button" className="btn block" disabled={!p || busy || !!blocked} onClick={submit}>
        {busy ? 'Сохраняю…' : action}
      </button>
    </Sheet>
  );
}
