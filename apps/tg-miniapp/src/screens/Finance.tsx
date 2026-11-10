import { ErrorBox, Skeleton } from '../components/ui';
import { money, moneyShort } from '../lib/format';
import { useAccounts, useToday, useTransactions } from '../lib/queries';
import type { Transaction } from '../lib/types';

const CAT_COLORS = ['#1f6fb2', '#e8710a', '#14a37f', '#8e5bd0', '#8a9199'];
const QUICK = ['Продукты', 'Такси', 'Кафе', 'Дом'];

const txType = (t: Transaction) => t.transaction_type || t.type;
const txCategory = (t: Transaction) => t.category_name || t.category || 'Прочее';

export function monthlyByCategory(txs: Transaction[], now = new Date()) {
  const sums = new Map<string, number>();
  for (const t of txs) {
    const d = new Date(t.occurred_at);
    if (txType(t) !== 'expense' || t.status === 'reversed') continue;
    if (d.getMonth() !== now.getMonth() || d.getFullYear() !== now.getFullYear()) continue;
    sums.set(txCategory(t), (sums.get(txCategory(t)) ?? 0) + t.amount_minor);
  }
  const sorted = [...sums.entries()].sort((a, b) => b[1] - a[1]);
  const top = sorted.slice(0, 4);
  const rest = sorted.slice(4).reduce((a, [, v]) => a + v, 0);
  if (rest > 0) top.push(['Прочее', rest]);
  return top.map(([name, minor], i) => ({ name, minor, color: CAT_COLORS[i] }));
}

export function FinanceScreen({ onQuickAdd }: { onQuickAdd: (prefill: string) => void }) {
  const accounts = useAccounts();
  const txs = useTransactions();
  const today = useToday();

  const accs = (accounts.data ?? []).filter((a) => !a.is_archived);
  const total = accs.reduce((s, a) => s + a.current_balance_minor, 0);
  const cats = monthlyByCategory(txs.data ?? []);
  const spent = today.data?.budget_summary.monthly_spent_minor ?? cats.reduce((s, c) => s + c.minor, 0);
  const limit = today.data?.budget_summary.monthly_limit_minor ?? 0;
  const denom = Math.max(limit, spent, 1);
  const monthName = new Date().toLocaleDateString('ru-RU', { month: 'long' });

  return (
    <>
      {accounts.isError && <ErrorBox error={accounts.error} onRetry={() => accounts.refetch()} />}
      <section className="card pad">
        <div className="small muted">Общий баланс</div>
        <div className="num" style={{ fontSize: 28, fontWeight: 700, marginTop: 4 }}>
          {accounts.isPending ? '…' : money(total)}
        </div>
        {accs.length > 0 ? (
          <div className="hscroll">
            {accs.map((a) => (
              <div key={a.id} className="acc">
                <div className="xsmall muted">{a.name}</div>
                <div className="num" style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{money(a.current_balance_minor, a.currency)}</div>
              </div>
            ))}
          </div>
        ) : (
          accounts.isSuccess && <div className="small muted" style={{ marginTop: 8 }}>Счетов пока нет — добавьте их в веб-версии.</div>
        )}
      </section>

      <section className="card pad" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="row-between">
          <span style={{ fontWeight: 600 }}>Расходы за {monthName}</span>
          {limit > 0 && <span className="small muted">{Math.round((spent / limit) * 100)}% бюджета</span>}
        </div>
        <div className="num" style={{ fontSize: 22, fontWeight: 700 }}>
          {moneyShort(spent)}
          {limit > 0 && <span className="small muted" style={{ fontWeight: 500 }}> из {moneyShort(limit)}</span>}
        </div>
        <div className="bar" role="img" aria-label="Расходы по категориям">
          {cats.map((c) => (
            <div key={c.name} style={{ height: 10, width: `${(c.minor / denom) * 100}%`, background: c.color }} />
          ))}
        </div>
        {cats.length > 0 ? (
          <div className="legend">
            {cats.map((c) => (
              <div key={c.name}>
                <span className="sw" style={{ background: c.color }} />
                <span className="name">{c.name}</span>
                <span className="muted num">{moneyShort(c.minor)}</span>
              </div>
            ))}
          </div>
        ) : (
          txs.isSuccess && <div className="small muted">В этом месяце расходов ещё нет</div>
        )}
      </section>

      <section className="quick-grid">
        {QUICK.map((c) => (
          <button key={c} type="button" onClick={() => onQuickAdd(` ${c.toLowerCase()}`)}>
            <span className="plus">+</span>
            {c}
          </button>
        ))}
      </section>

      <section className="card">
        <div className="card-title">Последние операции</div>
        {txs.isPending && <Skeleton h={160} />}
        {txs.isError && <ErrorBox error={txs.error} onRetry={() => txs.refetch()} />}
        {txs.isSuccess && txs.data.length === 0 && <div className="empty">Операций пока нет</div>}
        {(txs.data ?? []).slice(0, 8).map((t) => {
          const income = txType(t) === 'income';
          const title = txCategory(t);
          return (
            <div key={t.id} className="list-item">
              <div className="avatar" style={income ? { background: 'var(--oksoft)', color: 'var(--ok)' } : undefined}>
                {title.charAt(0).toUpperCase()}
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{title}</div>
                <div className="xsmall muted">
                  {new Date(t.occurred_at).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}
                  {t.account_name ? ` · ${t.account_name}` : ''}
                  {t.status === 'reversed' ? ' · сторнирована' : ''}
                </div>
              </div>
              <div className="num" style={{ fontSize: 14, fontWeight: 600, color: income ? 'var(--ok)' : undefined }}>
                {income ? '+' : '−'}{money(t.amount_minor, t.currency)}
              </div>
            </div>
          );
        })}
      </section>
    </>
  );
}
