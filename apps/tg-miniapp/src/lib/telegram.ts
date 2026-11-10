/** Thin typed wrapper around window.Telegram.WebApp (telegram-web-app.js). */

interface ThemeParams {
  bg_color?: string;
  secondary_bg_color?: string;
  text_color?: string;
  hint_color?: string;
  link_color?: string;
  button_color?: string;
  button_text_color?: string;
  section_bg_color?: string;
  section_separator_color?: string;
  destructive_text_color?: string;
}

interface BottomButton {
  setParams(p: { text?: string; color?: string; text_color?: string; is_active?: boolean; is_visible?: boolean }): void;
  show(): void;
  hide(): void;
  onClick(cb: () => void): void;
  offClick(cb: () => void): void;
  showProgress(leaveActive?: boolean): void;
  hideProgress(): void;
}

interface WebApp {
  initData: string;
  initDataUnsafe: { user?: { id: number; first_name?: string; username?: string } };
  colorScheme: 'light' | 'dark';
  themeParams: ThemeParams;
  platform: string;
  ready(): void;
  expand(): void;
  close(): void;
  onEvent(event: string, cb: () => void): void;
  MainButton: BottomButton;
  BackButton: { show(): void; hide(): void; onClick(cb: () => void): void; offClick(cb: () => void): void };
  HapticFeedback?: {
    impactOccurred(style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft'): void;
    notificationOccurred(type: 'error' | 'success' | 'warning'): void;
    selectionChanged(): void;
  };
  setHeaderColor?(color: string): void;
  setBackgroundColor?(color: string): void;
  disableVerticalSwipes?(): void;
}

declare global {
  interface Window {
    Telegram?: { WebApp?: WebApp };
  }
}

export const tg: WebApp | undefined = window.Telegram?.WebApp;

/** True only when opened inside Telegram with signed initData. */
export const insideTelegram = !!tg && !!tg.initData;

const THEME_MAP: Array<[keyof ThemeParams, string]> = [
  ['bg_color', '--bg'],
  ['secondary_bg_color', '--bg2'],
  ['section_bg_color', '--card'],
  ['text_color', '--text'],
  ['hint_color', '--hint'],
  ['link_color', '--link'],
  ['button_color', '--accent'],
  ['button_text_color', '--accent-text'],
  ['section_separator_color', '--line'],
  ['destructive_text_color', '--bad'],
];

export function applyTheme(): void {
  const root = document.documentElement;
  const dark = tg ? tg.colorScheme === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
  root.dataset.theme = dark ? 'dark' : 'light';
  if (!tg) return;
  for (const [key, cssVar] of THEME_MAP) {
    const v = tg.themeParams[key];
    if (v) root.style.setProperty(cssVar, v);
    else root.style.removeProperty(cssVar);
  }
}

export function initTelegram(): void {
  applyTheme();
  if (!tg) return;
  tg.ready();
  tg.expand();
  tg.disableVerticalSwipes?.();
  tg.onEvent('themeChanged', applyTheme);
}

export const haptic = {
  tap: () => tg?.HapticFeedback?.impactOccurred('light'),
  success: () => tg?.HapticFeedback?.notificationOccurred('success'),
  error: () => tg?.HapticFeedback?.notificationOccurred('error'),
  select: () => tg?.HapticFeedback?.selectionChanged(),
};
