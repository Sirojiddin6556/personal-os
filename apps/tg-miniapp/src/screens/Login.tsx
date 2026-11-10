import { useState, type FormEvent } from 'react';
import { IconCalendar } from '../components/ui';

interface Props {
  mode: 'link' | 'browser';
  telegramName?: string;
  busy: boolean;
  error?: string | null;
  onSubmit: (email: string, password: string) => void;
}

/**
 * Shown when the Telegram account is not linked yet (mode="link"),
 * or when the app is opened in a normal browser (mode="browser").
 */
export function LoginScreen({ mode, telegramName, busy, error, onSubmit }: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (email && password) onSubmit(email, password);
  };

  return (
    <form className="center-screen" onSubmit={submit}>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16, textAlign: 'center' }}>
        <div className="logo" style={{ color: 'var(--accent-text)' }}><IconCalendar size={44} /></div>
        <div>
          <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>
            {mode === 'link' ? `Привет${telegramName ? `, ${telegramName}` : ''}!` : 'Personal OS'}
          </h1>
          <p className="muted" style={{ margin: '8px 0 0', fontSize: 15, lineHeight: 1.45 }}>
            {mode === 'link'
              ? 'Войдите в свой аккаунт Personal OS один раз — дальше приложение будет открываться через Telegram без пароля.'
              : 'Мини-приложение рассчитано на запуск из Telegram-бота. В браузере можно войти по email.'}
          </p>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" className="input plain" type="email" autoComplete="username" inputMode="email"
            value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="password">Пароль</label>
          <input id="password" className="input plain" type="password" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && <div className="error-box" role="alert">{error}</div>}
      </div>

      <div style={{ marginTop: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <button type="submit" className="btn block" disabled={busy || !email || !password}>
          {busy ? 'Проверяю…' : mode === 'link' ? 'Привязать и войти' : 'Войти'}
        </button>
        {mode === 'link' && (
          <p className="xsmall muted" style={{ margin: 0, textAlign: 'center', lineHeight: 1.4 }}>
            Мы сохраним только ваш Telegram ID, чтобы узнавать вас при следующем запуске.
          </p>
        )}
      </div>
    </form>
  );
}
