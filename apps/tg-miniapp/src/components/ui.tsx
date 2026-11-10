import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { haptic, tg } from '../lib/telegram';

// ------------------------------------------------------------------ icons
type IconProps = { size?: number; stroke?: number };
const svg = (path: ReactNode) =>
  function Icon({ size = 22, stroke = 2 }: IconProps) {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={stroke}
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        {path}
      </svg>
    );
  };

export const IconSun = svg(<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>);
export const IconTasks = svg(<><rect x="3" y="3" width="18" height="18" rx="4" /><path d="m8 12 3 3 5-6" /></>);
export const IconWallet = svg(<><rect x="2" y="6" width="20" height="14" rx="3" /><path d="M2 10h20M16 15h2" /></>);
export const IconCalendar = svg(<><rect x="3" y="4" width="18" height="17" rx="3" /><path d="M8 2v4M16 2v4M3 10h18" /></>);
export const IconPlus = svg(<path d="M12 5v14M5 12h14" />);
export const IconCheck = svg(<path d="M20 6 9 17l-5-5" />);
export const IconSpark = svg(<><path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z" /><path d="M19 17v4M17 19h4" /></>);
export const IconBell = svg(<><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.9 1.9 0 0 0 3.4 0" /></>);
export const IconChevron = svg(<path d="m9 6 6 6-6 6" />);

// ------------------------------------------------------------------ toast
type ToastKind = 'ok' | 'error';
interface ToastState { text: string; kind: ToastKind; id: number }
const ToastCtx = createContext<(text: string, kind?: ToastKind) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<ToastState | null>(null);
  const timer = useRef<number>();
  const show = useCallback((text: string, kind: ToastKind = 'ok') => {
    if (kind === 'ok') haptic.success();
    else haptic.error();
    setToast({ text, kind, id: Date.now() });
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setToast(null), kind === 'error' ? 4000 : 2400);
  }, []);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {toast && (
        <div key={toast.id} role="status" className={`toast ${toast.kind === 'error' ? 'error' : ''}`}>
          {toast.kind === 'ok' && <span style={{ color: '#4cc68a', display: 'flex' }}><IconCheck size={18} stroke={2.5} /></span>}
          <span>{toast.text}</span>
        </div>
      )}
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);

// ------------------------------------------------------------------ sheet
/** Bottom sheet; wires Telegram's native BackButton to close it. */
export function Sheet({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const back = tg?.BackButton;
    if (!back) return;
    back.onClick(onClose);
    back.show();
    return () => {
      back.offClick(onClose);
      back.hide();
    };
  }, [onClose]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="overlay">
      <button type="button" className="overlay-bg" aria-label="Закрыть" onClick={onClose} />
      <div role="dialog" aria-modal="true" aria-label={label} className="sheet">
        <div className="grab" />
        {children}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ misc
export function ErrorBox({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const msg = error instanceof Error ? error.message : 'Не удалось загрузить данные';
  return (
    <div className="error-box row-between">
      <span>{msg}</span>
      {onRetry && <button type="button" className="link-btn" onClick={onRetry}>Повторить</button>}
    </div>
  );
}

export function Skeleton({ h = 120 }: { h?: number }) {
  return <div className="skeleton" style={{ height: h }} aria-hidden="true" />;
}
