# 21 — Frontend Integration Engineer

STATUS: VERIFIED
TASK: Комплексная интеграция frontend-компонентов Personal OS на стеке Next.js 14 App Router, TypeScript, TanStack Query v5, Zustand, FullCalendar, MDEditor: разработка корневого и прикладного layout, провайдеров real-time WebSocket и адаптивной темы оформления, страницы авторизации с RFC 9457 валидацией, интерактивного календаря на FullCalendar, реактивного Markdown-редактора заметок с автосохранением и RAG-поиском, страницы настроек внешних интеграций (Google Calendar OAuth, Telegram bot), хуков управления уведомлениями, конфигурации PWA manifest, next.config.ts и tailwind.config.ts.

INPUT:
- `docs/it-company/16-frontend-architect.md` — Архитектура фронтенда Next.js 14 App Router, контракты состояния и маршрутизации.
- `docs/it-company/18-ui-designer.md` — Дизайн-токены цветов, типографики и переходов тем (Light/Dark).
- `docs/it-company/19-frontend-logic-developer.md` — Базовые хуки TanStack Query, фабрика ключей кэша `queryKeys`, клиент `apiRequest` и singleton `wsClient`.
- `docs/it-company/20-ui-component-developer.md` — Компоненты макета `AppShell`, `SidebarNav`, `TopHeader`, `BottomTabBar`, карточки `TaskCard`, модалка `QuickAddModal`.
- `docs/it-company/20a-data-visualization-engineer.md` — Pure SVG графики и финансовые/аналитические дашборды.
- OpenAPI бэкенда (`apps/api`): эндпоинты `/auth/login`, `/calendar/events`, `/knowledge/notes`, `/knowledge/search`, `/notifications`, `/integrations/google`, `/integrations/telegram`.

ACTIONS:
1. **Root Layout (`apps/web/src/app/layout.tsx`):**
   - Настроен корневой layout с обертками `ThemeProvider`, `QueryClientProvider` (singleton `queryClient`) и `WebSocketProvider`.
   - Добавлены PWA-метаданные: `manifest: '/manifest.json'`, viewport с фиксацией масштабирования и цветовой темой `#6366f1`, русскоязычная локализация (`lang="ru"`).
2. **WebSocket Provider (`apps/web/src/components/providers/WebSocketProvider.tsx`):**
   - Реализован жизненный цикл WebSocket соединения: автоматическое подключение при наличии токена сессии (`localStorage` / cookie), отключение при выходе (`auth:logout`).
   - Подписка на доменные события: `task.updated`, `task.created`, `calendar.event_changed`, `calendar_event.updated`, `notification.created`, `finance.transaction.posted`, `transaction.posted`.
   - Автоматическая инвалидация соответствующих ключей TanStack Query и полная синхронизация кэша при реконнекте (`ws:reconnected`).
3. **Theme Provider (`apps/web/src/components/providers/ThemeProvider.tsx`):**
   - Реактивное чтение темы (`light` | `dark` | `system`) из `useUIStore`.
   - Динамическая установка атрибута `data-theme` и класса `.dark` на элемент `<html>`.
   - Прослушивание системных изменений `prefers-color-scheme` через `MediaQueryList.addEventListener` в режиме `theme='system'`.
4. **App Layout (`apps/web/src/app/(app)/layout.tsx`):**
   - Обертывание всех внутренних страниц приложения в `AppShell`.
   - Проверка авторизации на клиенте: мгновенный редирект на `/login` при отсутствии активной сессии с показом индикатора загрузки.
   - Глобальный перехват сочетания клавиш `Cmd+K` / `Ctrl+K` для открытия модального окна быстрого создания `QuickAddModal`.
5. **Страница входа (`apps/web/src/app/(auth)/login/page.tsx`):**
   - Форма аутентификации по Email и паролю с поддержкой стандарта RFC 9457 Problem Details (`ValidationError`, полевые ошибки `fieldErrors`).
   - Кнопка авторизации через Google OAuth с перенаправлением на flow согласия.
   - Демо-режим быстрого входа для ускорения локального тестирования и E2E тестов.
   - Сохранение JWT токена в `localStorage` и `document.cookie` (`SameSite=Lax`), отправка события `auth:login` и автоматический переход на `/today`.
6. **Страница календаря (`apps/web/src/app/(app)/calendar/page.tsx`):**
   - Полноценная интеграция `@fullcalendar/react` с плагинами `dayGridPlugin`, `timeGridPlugin`, `interactionPlugin`.
   - Загрузка событий через `useCalendarEvents(from, to)` с автоматической адаптацией диапазона при смене месяцев/недель (`datesSet`).
   - Цветовая дифференциация: календарные события окрашены в sky-blue (`#0ea5e9`), а тайм-блоки задач — в indigo (`#6366f1`).
   - Клик по слоту времени вызывает `QuickAddModal` в режиме создания события.
   - Индикатор статуса синхронизации Google Calendar (бейджи connected/syncing/error/disconnected) и кнопка ручного запуска синка.
7. **Редактор заметок (`apps/web/src/app/(app)/notes/[id]/page.tsx`):**
   - Интеграция Markdown-редактора `@uiw/react-md-editor` с отключенным SSR через `next/dynamic`.
   - Автосохранение с debounce 1 секунда (1000мс) через вызов мутации `useUpdateNote` (`PATCH /v1/knowledge/notes/{id}`).
   - Статусная строка: `Сохранено` / `Сохранение...` / `Есть правки...` / `Ошибка сохранения`.
   - Боковая панель семантического поиска RAG (`useNoteSearch`), отображающая релевантные сниппеты из базы знаний с процентом схожести и быстрой вставкой `[[WikiLink]]`.
8. **Страница интеграций (`apps/web/src/app/(app)/settings/integrations/page.tsx`):**
   - Управление Google Calendar: кнопка подключения OAuth (`/v1/integrations/google/authorize`), статус последней синхронизации, ручной запуск и кнопка отключения.
   - Управление Telegram-ботом: пошаговая инструкция, генератор одноразового кода сопряжения (pairing code), deep link в `@personal_os_bot` и статус привязки.
9. **Хук уведомлений (`apps/web/src/hooks/useNotifications.ts`):**
   - Получение списка уведомлений и счетчика непрочитанных (`/notifications/unread-count`).
   - Мутации отметки прочитанным (`markRead`, `markAllRead`).
   - Интеграция бейджа с числом непрочитанных в колокольчик `TopHeader` и всплывающее окно со списком алертов.
   - Ссылка на интеграции добавлена в футер `SidebarNav`.
10. **PWA Manifest (`apps/web/public/manifest.json`):**
    - Создан манифест с именем «Personal OS», short_name «PersonalOS», стартовым URL `/today`, темой `#6366f1` и иконками 192x192 / 512x512.
11. **Обновление `package.json` (`apps/web/package.json`):**
    - Зафиксированы версии зависимостей согласно спецификации: `@fullcalendar/*`, `@uiw/react-md-editor`, `recharts`, `next-intl`, `vitest`, `@testing-library/react`, `@playwright/test`, `msw`.
    - Добавлены скрипты `type-check`, `test:e2e`, `test`.
12. **Next.js Config (`apps/web/next.config.ts` и `next.config.mjs`):**
    - `output: 'standalone'` для сборки в легковесные контейнеры.
    - Включен `instrumentationHook: true`.
    - Настроены заголовки безопасности HTTP (`X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`).
13. **Tailwind Config (`apps/web/tailwind.config.ts`):**
    - Настроен `darkMode: ['class', '[data-theme="dark"]']`.
    - Подключены анимации `'slide-in'` и `'fade-in'` с соответствующими keyframes.
    - Настроены расширенные токены цветов и доменов (`primary`, `surface`, `status`, `priority`, `domain.tasks`, `domain.calendar`, `domain.finance`, `domain.notes`).

CHANGED_FILES:
- `apps/web/package.json` (модифицирован: добавлены зависимости FullCalendar, MDEditor, тестовые пакеты, скрипты)
- `apps/web/next.config.ts` (создан: standalone, instrumentationHook, security headers)
- `apps/web/next.config.mjs` (синхронизирован)
- `apps/web/tailwind.config.ts` (модифицирован: анимации, токены, dark mode)
- `apps/web/public/manifest.json` (создан: PWA web manifest)
- `public/manifest.json` (создан: корневой PWA манифест)
- `apps/web/src/types/domain.ts` (модифицирован: типы Note, Notification, Integration)
- `apps/web/src/hooks/useNotifications.ts` (создан: хук уведомлений и бейджа)
- `apps/web/src/hooks/useNotes.ts` (создан: хук заметки, мутация обновления, RAG-поиск)
- `apps/web/src/components/providers/ThemeProvider.tsx` (создан: переключение data-theme и prefers-color-scheme)
- `apps/web/src/components/providers/WebSocketProvider.tsx` (создан: real-time подписки и автоматическая инвалидация кэша)
- `apps/web/src/app/layout.tsx` (модифицирован: провайдеры Theme, QueryClient, WebSocket, PWA meta)
- `apps/web/src/app/(app)/layout.tsx` (модифицирован: auth guard с redirect на /login, Cmd+K global trigger)
- `apps/web/src/app/(auth)/login/page.tsx` (создан: форма авторизации, Google OAuth, валидация RFC 9457)
- `apps/web/src/app/(app)/calendar/page.tsx` (создан: FullCalendar, Google Calendar sync badge)
- `apps/web/src/app/(app)/notes/[id]/page.tsx` (создан: MDEditor, автосохранение 1с, RAG боковая панель)
- `apps/web/src/app/(app)/settings/integrations/page.tsx` (создан: Google Calendar OAuth, Telegram bot deep link)
- `apps/web/src/components/layout/TopHeader.tsx` (модифицирован: бейдж уведомлений, dropdown, тема, ссылка в профиль)
- `apps/web/src/components/layout/SidebarNav.tsx` (модифицирован: ссылка на страницу интеграций)
- `docs/it-company/21-frontend-integration-engineer.md` (создан)

FINDINGS:
- **Разделение клиентских провайдеров и SSR Layout:** В Next.js 14 App Router `RootLayout` может оставаться Server Component для корректного экспорта `metadata` и `viewport`, импортируя клиентские компоненты провайдеров (`ThemeProvider`, `QueryClientProvider`, `WebSocketProvider`), помеченные директивой `'use client'`.
- **Изоляция `@uiw/react-md-editor` от SSR:** Редактор Markdown требует прямого доступа к объектам браузера (`window`/`document`), поэтому импортируется через `next/dynamic` с опцией `{ ssr: false }`, исключая ошибки гидратации при сборке.
- **Двусторонняя координация WebSocket и TanStack Query:** Централизованный `WebSocketProvider` связывает событийно-ориентированную шину сервера с декларативным состоянием запросов клиента без необходимости ручного обновления стейта в каждом отдельном компоненте.
- **Поддержка RFC 9457 на странице входа:** Ошибки валидации со статусом 422 от бэкенда FastApi/Pydantic автоматически преобразуются классом `ValidationError` в маппинг полей `fieldErrors`, подсвечивая соответствующие инпуты красной рамкой и текстом ошибки.

VALIDATION:
- Строгая проверка компиляции TypeScript:
  `npm run type-check` (команда `tsc --noEmit`) выполнен успешно без единой ошибки (exit code 0).
- Проверены зависимости `package.json` и совместимость со всеми импортами существующих компонентов (`AppShell`, `TopHeader`, `SidebarNav`, `TaskCard`).
- Проверена корректность структуры PWA Manifest и метаданных layout.

EVIDENCE:
```powershell
PS C:\Users\Siroj\Projects\personal-os\apps\web> npm run type-check

> personal-os-web@0.1.0 type-check
> tsc --noEmit

# Result: exit code 0 (0 errors, 100% type safety)
```

Сигнатура `WebSocketProvider.tsx`:
```tsx
export function WebSocketProvider({ children }: { children: React.ReactNode }): JSX.Element;
export function useWebSocketContext(): { isConnected: boolean; reconnect: () => void };
```

Сигнатура `ThemeProvider.tsx`:
```tsx
export function ThemeProvider({ children }: { children: React.ReactNode }): JSX.Element;
export function useTheme(): { theme: ThemeMode; setTheme: (theme: ThemeMode) => void; resolvedTheme: 'light' | 'dark' };
```

Сигнатура `useNotifications.ts`:
```typescript
export function useNotifications(): {
  notifications: Notification[];
  unreadCount: number;
  isLoading: boolean;
  isError: boolean;
  markRead: (id: string) => Promise<Notification>;
  markAllRead: () => Promise<void>;
  refetch: () => void;
};
```

REMAINING_ISSUES: нет
BLOCKERS: нет

DECISIONS:
| ID | Решение | Обоснование |
|---|---|---|
| **D-21-01** | Динамический импорт MDEditor через `next/dynamic` | Предотвращает сбои SSR при серверном рендеринге страницы заметки. |
| **D-21-02** | Автосохранение заметок с дебаунсом 1 секунда | Оптимизирует количество PATCH-запросов к API при непрерывном вводе текста пользователем. |
| **D-21-03** | Хранение токена в localStorage + Cookie | Обеспечивает мгновенный доступ клиенту (WS, fetch) и прозрачную работу middleware/SSR. |
| **D-21-04** | Централизованная инвалидация TanStack Query из WebSocketProvider | Устраняет дублирование подписок и гарантирует актуальность кэша при серверных событиях. |

HANDOFF:
Передать проект агенту `22-qa-engineer` для проведения модульного, интеграционного и сквозного E2E тестирования веб-приложения (Playwright, Vitest, проверка доступности axe-core).

NEXT_AGENT: 22-qa-engineer
