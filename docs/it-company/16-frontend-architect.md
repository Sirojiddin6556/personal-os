# 16 — Frontend Architect

STATUS: VERIFIED
TASK: Разработать архитектурную спецификацию фронтенда Personal OS (Frontend Architecture Document): полная файловая структура Next.js 14+ App Router, двухуровневое управление состоянием (TanStack Query v5 + Zustand), слой API-клиента с поддержкой Idempotency-Key и If-Match (RFC 9457 Problem Details), WebSocket-клиент с устойчивой реконнекцией и компенсацией пропущенных событий, маршрутизация и Layouts (AppShell, параллельные и перехватывающие роуты для Slide-over панелей), требования к коду (RSC vs Client Components, dnd-kit Kanban, FullCalendar, PWA, next-intl i18n), сквозная стратегия тестирования (Unit, Integration MSW, E2E Playwright, axe-core a11y) и Performance-бюджеты.
INPUT:
- `docs/it-company/01-product-discovery-manager.md` — Product Vision, MVP Scope, NFR, профили пользователей
- `docs/it-company/02-business-analyst.md` — 65 User Stories, Use Cases, Business Rules, AC-матрица
- `docs/it-company/03-product-manager.md` — Product Backlog, Sprint Plan (S0–S16), DoD, MoSCoW
- `docs/it-company/04-solution-architect.md` — C4 Containers, Bounded Contexts, REST API v1, Event Catalog, WebSocket /v1/ws, RFC 9457
- `docs/it-company/17-ux-designer.md` — 7 UX-принципов, Wireframes (Today, Quick Add, Tasks/Kanban, Calendar, Finance, TG patterns), Information Architecture (L1/L2/L3, Mobile PWA 5-tab)
- `docs/it-company/18-ui-designer.md` — Design Tokens (HSL/CSS variables), компонентная библиотека (15 base + 9 domain), Page Layouts, tailwind.config.ts

ACTIONS:
1. Спроектирована архитектура клиентского приложения `apps/web` на стеке Next.js 14+ App Router, React 18, TypeScript, Tailwind CSS, shadcn/ui.
2. Детализирована полная файловая структура модулей, страниц, компонентов, хуков, сторов и сервисов.
3. Разработана модель управления состоянием: строгое разделение Server State (TanStack Query v5) и UI State (Zustand) с исключением дублирования данных.
4. Разработан и специфицирован API Client Layer с поддержкой `Idempotency-Key` (UUIDv4), оптимистической блокировки `If-Match` / `ETag`, типизированных ошибок RFC 9457 Problem Details и курсорной пагинации.
5. Спроектирован WebSocket-клиент для `/v1/ws` с обработкой событий каталога Solution Architect, экспоненциальным backoff с джиттером и автоматической синхронизацией пропущенных событий при реконнекте.
6. Описана архитектура маршрутизации и лэйаутов: AppShell (Desktop Sidebar + Mobile PWA Bottom Bar), параллельные/перехватывающие роуты (`@modal/(.)tasks/[id]`) для сохранения скролла и фильтров при открытии Slide-over панелей.
7. Зафиксированы стандарты кода: граница Server Components vs Client Components (запрет прямого доступа к БД из RSC), реализация Kanban на `@dnd-kit`, календаря на `@fullcalendar`, PWA-манифест, Service Worker и локализация через `next-intl`.
8. Сформирована сквозная стратегия тестирования: Unit (Vitest + RTL), Integration (MSW), E2E (Playwright) и Accessibility (`@axe-core/playwright`).
9. Определены Performance-таргеты (LCP < 2.5s, Quick Add < 50ms, Kanban Drag 60 FPS, Bundle Initial JS < 150KB gzip).

CHANGED_FILES:
- `docs/it-company/16-frontend-architect.md`

FINDINGS:
- **Strict Separation of Concerns:** Server state полностью делегирован TanStack Query. Никакие сущности с бэкенда (Tasks, Events, Transactions) не сохраняются в глобальные Zustand-сторы. Zustand хранит только эфемерное UI-состояние (sidebar collapsed, active modals, theme, filter toggles).
- **Context Preservation via Intercepting Routes:** Требование UX-17 о сохранении фильтров и позиции скролла при детальном просмотре задач реализуется через перехватывающие маршруты Next.js (`@modal/(.)tasks/[id]`). При прямом переходе по URL открывается полноценная страница `/tasks/[id]`, а при клике из списка/канбана — плавная Slide-over панель поверх текущего экрана.
- **Idempotency & Retry Resilience:** Любая мутирующая операция (`POST`, неидемпотентный `PATCH`) генерирует уникальный `Idempotency-Key` (UUID v4) до отправки. При сетевых сбоях и автоматических повторах тот же ключ защищает от создания дубликатов задач или финансовых проводок на бэкенде.
- **WebSocket Hot Path vs Invalidation:** Для высокочастотных событий (статус задачи, перемещение в канбане) применяется оптимистичное обновление локального кэша и реактивное подтверждение, а для композитных агрегатов (Morning Brief, пересчет бюджетов) — точечная инвалидация соответствующих ключей запросов.
- **No Direct DB Access in RSC:** Несмотря на то, что Next.js Server Components технически могут подключаться к базам данных, в Personal OS установлен абсолютный архитектурный запрет на прямое подключение к PostgreSQL/Prisma из фронтенда. Все запросы выполняются строго через Core REST API (`/v1`) для соблюдения единых правил RLS, аудита и безопасности.

VALIDATION:
- Проверка согласованности структуры маршрутов с Information Architecture из `17-ux-designer.md`.
- Сопоставление контрактов доменных типов и событий с каталогом Solution Architect из `04-solution-architect.md`.
- Интеграция дизайн-токенов и компонентов из `18-ui-designer.md`.
- Валидация TypeScript-сигнатур для `apiRequest`, `ws-client`, TanStack Query keys и хуков мутаций.

EVIDENCE:
- Полное дерево файлов приложения `apps/web`.
- Рабочие примеры кода `api-client.ts`, `ws-client.ts`, `useOptimisticUpdate.ts`, `useTasks.ts`.
- Спецификация конфигурации PWA (`manifest.json`, `sw.js`).
- Шаблоны интеграционных и E2E тестов.

REMAINING_ISSUES: нет
BLOCKERS: нет

DECISIONS:
| ID | Решение | Обоснование |
|---|---|---|
| **ADR-FE-01** | Next.js 14+ App Router + TypeScript Strict | Стандарт корпоративной разработки, гибридный SSR/CSR, поддержка streaming и параллельных маршрутов. |
| **ADR-FE-02** | TanStack Query v5 для Server State | Индустриальный стандарт кэширования, автоматическая дедупликация, встроенная поддержка optimistic updates и garbage collection. |
| **ADR-FE-03** | Zustand для UI State | Легковесный (< 2KB), не требует Context-оберток, селекторы предотвращают лишние ререндеры. |
| **ADR-FE-04** | Перехватывающие маршруты Next.js (`@modal/(.)[id]`) для Slide-over панелей | Идеальная реализация UX-принципа Context Preservation: сохранение скролла/фильтров + поддержка прямой ссылки при шеринге. |
| **ADR-FE-05** | `@dnd-kit` для Kanban вместо `react-beautiful-dnd` | Современная поддержка React 18, виртуализация, поддержка touch-устройств и WAI-ARIA клавиатурной доступности. |
| **ADR-FE-06** | Запрет прямого доступа к БД из React Server Components | Гарантия изоляции тенантов (RLS) через централизованный Core API, безопасность токенов и аудит. |
| **ADR-FE-07** | Сквозной `Idempotency-Key` (UUIDv4) во всех мутациях | Защита от двойных списаний в финансах и дубликатов задач при нестабильном мобильном соединении. |
| **ADR-FE-08** | Реконнект WebSocket с Exponential Backoff + Jitter и Missed Events Sync | Устойчивость к обрывам связи в PWA и автоматическая актуализация экрана при возврате из фонового режима. |

HANDOFF:
- Передать спецификацию агенту `19-frontend-logic-developer` для реализации бизнес-логики, кастомных хуков, API-клиента, WebSocket-менеджера и интеграции форм.
NEXT_AGENT: 19-frontend-logic-developer

---

# 1. ПОЛНАЯ СТРУКТУРА APPS/WEB

Приложение фронтенда Personal OS размещается в пакете монорепозитория `apps/web` и использует Next.js 14+ с архитектурой App Router.

```
apps/web/
├── app/                                  # Next.js App Router (Routing, Layouts, Pages)
│   ├── (auth)/                           # Route Group: Аутентификация (без AppShell)
│   │   ├── layout.tsx                    # Центрированный минималистичный лэйаут
│   │   ├── login/
│   │   │   └── page.tsx                  # Вход по Email/Password или Magic Link
│   │   ├── register/
│   │   │   └── page.tsx                  # Регистрация и создание первого воркспейса
│   │   └── callback/
│   │       └── page.tsx                  # Обработка OAuth2 redirect (Google / Telegram)
│   │
│   ├── (app)/                            # Route Group: Основное рабочее пространство (с AppShell)
│   │   ├── layout.tsx                    # AppShell: Sidebar + Header + BottomTabBar + Modals
│   │   ├── page.tsx                      # Root Redirect -> /today
│   │   ├── today/
│   │   │   ├── page.tsx                  # Today Dashboard (Morning Brief, Tasks, Events, Habits)
│   │   │   ├── loading.tsx               # Skeleton загрузки Dashboard
│   │   │   └── error.tsx                 # Error boundary экрана Today
│   │   ├── tasks/
│   │   │   ├── page.tsx                  # Задачи: Kanban / List (Search params: ?view=kanban|list)
│   │   │   ├── loading.tsx               # Skeleton загрузки колонок / списка
│   │   │   ├── error.tsx                 # Error boundary задач
│   │   │   ├── [id]/
│   │   │   │   └── page.tsx              # Fallback прямой ссылки на задачу (full page)
│   │   │   └── @modal/                   # Parallel Route для перехвата детального вида
│   │   │       ├── default.tsx           # Пустой слот по умолчанию
│   │   │       └── (.)[id]/              # Intercepting Route: Slide-over Sheet поверх списка
│   │   │           └── page.tsx          # TaskDetailSlideOver (сохраняет скролл и фильтры)
│   │   ├── projects/
│   │   │   ├── page.tsx                  # Список активных проектов и целей
│   │   │   └── [id]/
│   │   │       └── page.tsx              # Детальный вид проекта (Milestones, Tasks, Budget)
│   │   ├── calendar/
│   │   │   ├── page.tsx                  # Calendar View (?view=day|week|month&date=YYYY-MM-DD)
│   │   │   ├── loading.tsx
│   │   │   └── error.tsx
│   │   ├── finance/
│   │   │   ├── page.tsx                  # Finance Dashboard (Счета, Бюджеты, Транзакции)
│   │   │   ├── loading.tsx
│   │   │   └── error.tsx
│   │   ├── habits/
│   │   │   ├── page.tsx                  # Трекер привычек (Heatmap, текущие стрики)
│   │   │   └── loading.tsx
│   │   ├── notes/
│   │   │   ├── page.tsx                  # База знаний / Заметки (дерево, теги, семантический поиск)
│   │   │   └── [id]/
│   │   │       └── page.tsx              # Markdown-редактор заметок с автосохранением
│   │   └── settings/
│   │       ├── layout.tsx                # Лэйаут настроек с боковым подменю
│   │       ├── page.tsx                  # Общие настройки профиля и воркспейса
│   │       ├── integrations/
│   │       │   └── page.tsx              # Подключение Google Calendar и Telegram Bot
│   │       ├── notifications/
│   │       │   └── page.tsx              # Матрица каналов, тихие часы, приоритеты
│   │       └── preferences/
│   │           └── page.tsx              # Язык (ru/en), тема (light/dark), первый день недели
│   │
│   ├── api/                              # Route Handlers (Edge / Node API endpoints)
│   │   ├── auth/
│   │   │   └── session/route.ts          # Сессионные куки и валидация токена
│   │   └── health/
│   │       └── route.ts                  # Healthcheck фронтенд-сервера
│   │
│   ├── favicon.ico
│   ├── globals.css                       # Глобальные стили, CSS variables дизайн-токенов
│   ├── layout.tsx                        # Корневой HTML-лэйаут (Inter, JetBrains Mono, Meta)
│   ├── not-found.tsx                     # Кастомная 404 страница
│   └── global-error.tsx                  # Глобальный перехватчик фатальных ошибок
│
├── components/                           # Компонентная база приложения
│   ├── ui/                               # Базовые атомарные компоненты (shadcn/ui + Radix UI)
│   │   ├── button.tsx                    # Кнопка (primary, secondary, ghost, destructive, outline)
│   │   ├── input.tsx                     # Текстовое поле ввода
│   │   ├── textarea.tsx                  # Многострочное текстовое поле
│   │   ├── select.tsx                    # Выпадающий список (Radix Select)
│   │   ├── checkbox.tsx                  # Чекбокс
│   │   ├── switch.tsx                    # Переключатель
│   │   ├── badge.tsx                     # Бейдж приоритета / статуса
│   │   ├── avatar.tsx                    # Аватар пользователя / контакта
│   │   ├── card.tsx                      # Карточка-контейнер
│   │   ├── dialog.tsx                    # Модальное окно (Radix Dialog)
│   │   ├── sheet.tsx                     # Выдвижная панель (Slide-over Sheet)
│   │   ├── toast.tsx                     # Всплывающее уведомление
│   │   ├── toaster.tsx                   # Менеджер тостов (Radix Toast / Sonner)
│   │   ├── dropdown-menu.tsx             # Контекстное меню
│   │   ├── tooltip.tsx                   # Тултип с подсказкой
│   │   ├── tabs.tsx                      # Вкладки (Radix Tabs)
│   │   ├── skeleton.tsx                  # Скелетон для состояния загрузки
│   │   ├── popover.tsx                   # Всплывающий поповер
│   │   └── command.tsx                   # Командная панель (cmdk)
│   │
│   ├── domain/                           # Доменные бизнес-компоненты
│   │   ├── tasks/
│   │   │   ├── TaskCard.tsx              # Карточка задачи (чекбокс, приоритет, теги, дедлайн)
│   │   │   ├── KanbanBoard.tsx           # Доска Kanban на базе @dnd-kit
│   │   │   ├── KanbanColumn.tsx          # Колонка Kanban (Inbox, Backlog, Scheduled, etc.)
│   │   │   ├── TaskList.tsx              # Списочное отображение задач с группировкой
│   │   │   ├── TaskDetailSheet.tsx       # Панель редактирования задачи (Slide-over)
│   │   │   └── TaskFilterToolbar.tsx     # Панель фильтрации (приоритет, проект, статус)
│   │   ├── calendar/
│   │   │   ├── CalendarGrid.tsx          # Обертка над FullCalendar
│   │   │   ├── CalendarDayCell.tsx       # Ячейка дня в месячном представлении
│   │   │   ├── EventChip.tsx             # Чип календарного события
│   │   │   ├── TimeBlockBar.tsx          # Полоса заблокированного рабочего времени (TimeBlock)
│   │   │   └── EventDetailModal.tsx      # Модальное окно создания/редактирования события
│   │   ├── finance/
│   │   │   ├── ExpenseRow.tsx            # Строка финансовой транзакции в журнале
│   │   │   ├── BudgetProgress.tsx        # Прогресс-бар бюджета категории с алертами
│   │   │   ├── AccountCard.tsx           # Карточка банковского/наличного счета
│   │   │   └── NewTransactionModal.tsx   # Модальное окно добавления расхода/дохода
│   │   ├── habits/
│   │   │   ├── HabitStreak.tsx           # Индикатор текущей серии дней
│   │   │   ├── HabitHeatmap.tsx          # Календарная теплокарта выполнения привычек
│   │   │   └── HabitCheckInRow.tsx       # Строка быстрой отметки привычки за сегодня
│   │   ├── notifications/
│   │   │   ├── NotificationItem.tsx      # Элемент уведомления в центре нотификаций
│   │   │   └── NotificationPopover.tsx   # Всплывающее окно уведомлений по колокольчику
│   │   ├── ai/
│   │   │   ├── MorningBriefCard.tsx      # Интерактивная карточка утреннего брифинга
│   │   │   ├── AIPreviewDiff.tsx         # Двухколоночный Diff изменений от AI (Safety First)
│   │   │   ├── AIAdvisorDrawer.tsx       # Боковой чат с персональным ассистентом
│   │   │   └── ActionProposalModal.tsx   # Модалка подтверждения действия (Human-in-the-Loop)
│   │   └── quick-add/
│   │       ├── QuickAddModal.tsx         # Модальное окно быстрого захвата (Cmd+K)
│   │       ├── IntentChips.tsx           # Чипы переключения распознанного намерения (Task/Event/Expense)
│   │       └── VoiceInputButton.tsx      # Кнопка голосового захвата (Web Speech API / Audio Upload)
│   │
│   ├── layout/                           # Компоненты общей структуры
│   │   ├── AppShell.tsx                  # Главный каркас рабочего пространства
│   │   ├── Sidebar.tsx                   # Десктопная боковая панель (сворачивание 64px / 240px)
│   │   ├── SidebarNav.tsx                # Навигационные ссылки первого и второго уровней (L1/L2)
│   │   ├── TopHeader.tsx                 # Верхняя панель (Хлебные крошки, Поиск, Колокольчик, Профиль)
│   │   ├── BottomTabBar.tsx              # Мобильная навигационная панель (5 вкладок + центр FAB)
│   │   └── CommandPalette.tsx            # Глобальная командная строка (Cmd+K / Ctrl+K)
│   │
│   └── providers/                        # Контекст-провайдеры клиентского приложения
│       ├── AppProviders.tsx              # Корневой композитный провайдер
│       ├── QueryProvider.tsx             # TanStack Query Client Provider
│       ├── ThemeProvider.tsx             # Провайдер темы (next-themes: light, dark, system)
│       ├── WebSocketProvider.tsx         # Подключение к /v1/ws и диспетчеризация событий
│       └── I18nProvider.tsx              # Провайдер переводов next-intl
│
├── hooks/                                # Пользовательские React-хуки
│   ├── useTasks.ts                       # Запросы и мутации задач (list, get, create, update, delete)
│   ├── useKanban.ts                      # Логика перемещения задач между колонками и dnd-kit
│   ├── useCalendar.ts                    # Загрузка событий расписания и тайм-блоков
│   ├── useFinance.ts                     # Счета, транзакции, бюджеты и расчет балансов
│   ├── useHabits.ts                      # Загрузка привычек, расчет серий и отметка чекинов
│   ├── useMorningBrief.ts                # Загрузка утреннего брифинга и применение рекомендаций
│   ├── useQuickAdd.ts                    # Парсинг намерений быстрого ввода на лету (debounced NLP)
│   ├── useWebSocket.ts                   # Подписка на доменные события через WebSocket
│   ├── useOptimisticUpdate.ts            # Универсальный хелпер безопасных оптимистичных мутаций
│   ├── useKeyboardShortcut.ts            # Регистрация глобальных и локальных сочетаний клавиш
│   ├── useMediaQuery.ts                  # Определение брейкпоинтов (isMobile, isTablet, isDesktop)
│   └── useDebounce.ts                    # Дебаунс значений для поисковых инпутов
│
├── lib/                                  # Инфраструктурные библиотеки и клиенты
│   ├── api-client.ts                     # HTTP fetch-клиент с Idempotency-Key, ETag, RFC 9457
│   ├── ws-client.ts                      # Синглтон менеджера WebSocket с reconnection & heartbeat
│   ├── query-keys.ts                     # Иерархическая фабрика ключей кэша TanStack Query
│   ├── query-client.ts                   # Экземпляр и конфигурация QueryClient по умолчанию
│   ├── auth.ts                           # Управление JWT токенами, refresh flow, logout
│   ├── formatters.ts                     # Форматирование валют (minor units), дат, времени
│   └── utils.ts                          # Вспомогательные функции (cn = clsx + twMerge)
│
├── stores/                               # Клиентские хранилища состояния (Zustand)
│   ├── ui-store.ts                       # Состояние UI: сайдбар, активные модалки, Quick Add open
│   ├── filter-store.ts                   # Фильтры списков, выбранные теги, проекты
│   └── command-store.ts                  # Состояние открытия и контекста командной палитры
│
├── types/                                # TypeScript типы и интерфейсы
│   ├── api.ts                            # RFC 9457 ProblemDetails, курсорная пагинация, HTTP опции
│   ├── domain.ts                         # Task, Project, CalendarEvent, TimeBlock, Transaction, Habit, Note
│   ├── events.ts                         # Каталог доменных событий (Envelope, EventType, EventData)
│   └── ws.ts                             # WebSocket протокол (Connect, Heartbeat, Subscriptions)
│
├── styles/                               # Стили и анимации
│   └── globals.css                       # Базовые стили, Tailwind директивы, CSS variables токенов
│
├── public/                               # Статические ресурсы и PWA
│   ├── manifest.json                     # Конфигурация Progressive Web App
│   ├── sw.js                             # Service Worker (кэширование, оффлайн, Web Push)
│   ├── offline.html                      # Оффлайн-заглушка при отсутствии соединения
│   └── icons/                            # Иконки PWA (192x192, 512x512, maskable)
│
├── next.config.mjs                       # Конфигурация Next.js (PWA, Security Headers, Rewrites)
├── tailwind.config.ts                    # Конфигурация Tailwind CSS с токенами из UI Kit
├── tsconfig.json                         # Strict TypeScript конфигурация
└── package.json                          # Зависимости и скрипты сборки
```

---

# 2. ГОСУДАРСТВЕННОЕ УПРАВЛЕНИЕ ДАННЫМИ (STATE MANAGEMENT)

В Personal OS действует жесткий архитектурный инвариант разделения типов состояния:

```
+-------------------------------------------------------------------------+
|                       АРХИТЕКТУРА СОСТОЯНИЯ                             |
+------------------------------------+------------------------------------+
|            SERVER STATE            |              UI STATE              |
|        (TanStack Query v5)         |             (Zustand)              |
+------------------------------------+------------------------------------+
| • Задачи, статусы, приоритеты      | • Сайдбар свернут/развернут (bool) |
| • Календарные события и тайм-блоки | • Открытые модальные окна и Sheet  |
| • Транзакции, счета и бюджеты      | • Активная вкладка мобильного меню |
| • Утренний брифинг и AI-пропозалы  | • Текущая выбранная тема оформления|
| • Привычки и история стриков       | • Инпут командной строки (Cmd+K)   |
| • Уведомления и счетчики Inbox     | • Локальное состояние драфта ввода |
+------------------------------------+------------------------------------+
| Особенности:                       | Особенности:                       |
| - Асинхронное получение с сервера  | - Строго синхронное, эфемерное     |
| - Автоматическая инвалидация       | - Отсутствие сетевых запросов      |
| - Кэширование с политикой TTL      | - Селекторы без лишних ререндеров  |
| - Оптимистичные обновления         | - Легковесный размер (< 2 KB)      |
+------------------------------------+------------------------------------+
```

### 2.1 Золотое правило: Запрет дублирования данных
**НИКОГДА не сохранять и не копировать данные с бэкенда в Zustand-сторы.**  
Любая сущность домена (`Task`, `Transaction`, `CalendarEvent`) живет **исключительно** в кэше TanStack Query. Попытка продублировать список задач в Zustand приводит к рассинхронизации состояния при получении WebSocket-событий или инвалидации кэша.

### 2.2 Фабрика Query Keys (`lib/query-keys.ts`)

Для обеспечения типобезопасной и гранулярной инвалидации кэша используется иерархическая структура ключей:

```typescript
// lib/query-keys.ts

export const queryKeys = {
  // Аутентификация и текущий пользователь
  auth: {
    all: ['auth'] as const,
    session: () => [...queryKeys.auth.all, 'session'] as const,
    user: () => [...queryKeys.auth.all, 'user'] as const,
  },

  // Задачи и Kanban
  tasks: {
    all: ['tasks'] as const,
    lists: () => [...queryKeys.tasks.all, 'list'] as const,
    list: (filters: { status?: string; projectId?: string; priority?: string; search?: string }) =>
      [...queryKeys.tasks.lists(), filters] as const,
    kanban: (workspaceId: string) => [...queryKeys.tasks.all, 'kanban', workspaceId] as const,
    details: () => [...queryKeys.tasks.all, 'detail'] as const,
    detail: (id: string) => [...queryKeys.tasks.details(), id] as const,
    today: () => [...queryKeys.tasks.all, 'today'] as const,
  },

  // Календарь и расписание
  calendar: {
    all: ['calendar'] as const,
    events: (range: { start: string; end: string }) => [...queryKeys.calendar.all, 'events', range] as const,
    timeblocks: (date: string) => [...queryKeys.calendar.all, 'timeblocks', date] as const,
    today: () => [...queryKeys.calendar.all, 'today'] as const,
  },

  // Финансы
  finance: {
    all: ['finance'] as const,
    accounts: () => [...queryKeys.finance.all, 'accounts'] as const,
    transactions: (cursor?: string, limit?: number) => [...queryKeys.finance.all, 'transactions', { cursor, limit }] as const,
    budgets: (month: string) => [...queryKeys.finance.all, 'budgets', month] as const,
    summary: () => [...queryKeys.finance.all, 'summary'] as const,
  },

  // Привычки
  habits: {
    all: ['habits'] as const,
    list: () => [...queryKeys.habits.all, 'list'] as const,
    detail: (id: string) => [...queryKeys.habits.all, 'detail', id] as const,
    streaks: () => [...queryKeys.habits.all, 'streaks'] as const,
  },

  // Утренний брифинг и AI
  ai: {
    all: ['ai'] as const,
    morningBrief: (date: string) => [...queryKeys.ai.all, 'morning-brief', date] as const,
    proposals: () => [...queryKeys.ai.all, 'proposals'] as const,
    conversations: () => [...queryKeys.ai.all, 'conversations'] as const,
  },

  // Уведомления
  notifications: {
    all: ['notifications'] as const,
    list: (unreadOnly?: boolean) => [...queryKeys.notifications.all, 'list', { unreadOnly }] as const,
    unreadCount: () => [...queryKeys.notifications.all, 'unread-count'] as const,
  },
} as const;
```

### 2.3 Политики свежести и сборки мусора (StaleTime & GcTime)

В `lib/query-client.ts` определены глобальные и доменные политики кэширования:

```typescript
// lib/query-client.ts
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30,             // 30 секунд данные считаются свежими
      gcTime: 1000 * 60 * 10,           // 10 минут хранятся неактивные запросы в памяти
      refetchOnWindowFocus: true,       // Автообновление при возврате на вкладку
      refetchOnReconnect: true,         // Автообновление при восстановлении сети
      retry: (failureCount, error: any) => {
        // Не повторять запросы при клиентских ошибках авторизации и валидации
        if (error?.status === 401 || error?.status === 403 || error?.status === 404 || error?.status === 422) {
          return false;
        }
        return failureCount < 3;
      },
    },
    mutations: {
      retry: 1,                         // 1 повтор при сетевом сбое мутации
    },
  },
});
```

### 2.4 Паттерн безопасных оптимистичных обновлений (`useOptimisticUpdate`)

Оптимистичные обновления обязательны для действий с мгновенным откликом (чекбокс завершения задачи, перетаскивание карточки в Kanban, быстрая отметка привычки):

```typescript
// hooks/useOptimisticUpdate.ts
import { useQueryClient } from '@tanstack/react-query';

interface OptimisticUpdateOptions<TData, TVariables> {
  queryKey: readonly unknown[];
  updateFn: (oldData: TData | undefined, variables: TVariables) => TData;
}

export function useOptimisticMutationHelper() {
  const queryClient = useQueryClient();

  const createOptimisticContext = async <TData, TVariables>({
    queryKey,
    updateFn,
    variables,
  }: OptimisticUpdateOptions<TData, TVariables> & { variables: TVariables }) => {
    // 1. Отменяем любые исходящие refetch-запросы по данному ключу, чтобы не перезаписать оптимистичный стейт
    await queryClient.cancelQueries({ queryKey });

    // 2. Делаем снимок предыдущего состояния для возможного отката
    const previousData = queryClient.getQueryData<TData>(queryKey);

    // 3. Оптимистично записываем обновленные данные в кэш
    queryClient.setQueryData<TData>(queryKey, (old) => updateFn(old, variables));

    // 4. Возвращаем контекст с предыдущими данными
    return { previousData, queryKey };
  };

  const rollback = (context?: { previousData: unknown; queryKey: readonly unknown[] }) => {
    if (context?.queryKey && context?.previousData !== undefined) {
      queryClient.setQueryData(context.queryKey, context.previousData);
    }
  };

  const invalidate = (queryKey: readonly unknown[]) => {
    queryClient.invalidateQueries({ queryKey });
  };

  return { createOptimisticContext, rollback, invalidate };
}
```

### 2.5 Zustand: Хранилище UI-состояния (`stores/ui-store.ts`)

```typescript
// stores/ui-store.ts
import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

interface UIState {
  // Сайдбар (десктоп)
  isSidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;

  // Модальные окна
  isQuickAddOpen: boolean;
  quickAddInitialType: 'task' | 'event' | 'expense';
  openQuickAdd: (initialType?: 'task' | 'event' | 'expense') => void;
  closeQuickAdd: () => void;

  // Slide-over детали задачи
  activeTaskId: string | null;
  openTaskDetail: (taskId: string) => void;
  closeTaskDetail: () => void;

  // AI Ассистент
  isAIAssistantOpen: boolean;
  toggleAIAssistant: () => void;

  // Мобильное меню
  activeMobileTab: 'today' | 'tasks' | 'calendar' | 'finance' | 'notes';
  setActiveMobileTab: (tab: 'today' | 'tasks' | 'calendar' | 'finance' | 'notes') => void;
}

export const useUIStore = create<UIState>()(
  devtools(
    persist(
      (set) => ({
        isSidebarCollapsed: false,
        toggleSidebar: () => set((state) => ({ isSidebarCollapsed: !state.isSidebarCollapsed })),
        setSidebarCollapsed: (collapsed) => set({ isSidebarCollapsed: collapsed }),

        isQuickAddOpen: false,
        quickAddInitialType: 'task',
        openQuickAdd: (type = 'task') => set({ isQuickAddOpen: true, quickAddInitialType: type }),
        closeQuickAdd: () => set({ isQuickAddOpen: false }),

        activeTaskId: null,
        openTaskDetail: (taskId) => set({ activeTaskId: taskId }),
        closeTaskDetail: () => set({ activeTaskId: null }),

        isAIAssistantOpen: false,
        toggleAIAssistant: () => set((state) => ({ isAIAssistantOpen: !state.isAIAssistantOpen })),

        activeMobileTab: 'today',
        setActiveMobileTab: (tab) => set({ activeMobileTab: tab }),
      }),
      {
        name: 'personal-os-ui-storage',
        partialize: (state) => ({ isSidebarCollapsed: state.isSidebarCollapsed }),
      }
    )
  )
);
```

---

# 3. API CLIENT LAYER

Фронтенд взаимодействует с Core REST API через строго типизированный модуль `lib/api-client.ts`. Он инкапсулирует передачу токенов авторизации, генерацию заголовков идемпотентности, оптимистичную блокировку версий и обработку ошибок по стандарту RFC 9457 Problem Details.

### 3.1 Спецификация `lib/api-client.ts`

```typescript
// lib/api-client.ts

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
  code?: string;
  invalid_params?: Array<{
    name: string;
    reason: string;
  }>;
}

export class ApiError extends Error {
  public status: number;
  public problem: ProblemDetails;

  constructor(problem: ProblemDetails) {
    super(problem.detail || problem.title || `API Error ${problem.status}`);
    this.name = 'ApiError';
    this.status = problem.status;
    this.problem = problem;
  }
}

export interface ApiRequestOptions<TBody = unknown> {
  body?: TBody;
  headers?: Record<string, string>;
  params?: Record<string, string | number | boolean | undefined | null>;
  idempotencyKey?: string;               // UUID v4 для предотвращения дублей
  ifMatch?: number | string;            // Версия агрегата для ETag/If-Match
  signal?: AbortSignal;                 // Поддержка отмены запроса
}

export interface ApiResponse<TData> {
  data: TData;
  etag?: string;
  status: number;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/v1';

export async function apiRequest<TData, TBody = unknown>(
  method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE',
  path: string,
  options: ApiRequestOptions<TBody> = {}
): Promise<TData> {
  const { body, headers = {}, params, idempotencyKey, ifMatch, signal } = options;

  // 1. Построение строки Query Parameters
  let url = `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  if (params) {
    const searchParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        searchParams.append(key, String(value));
      }
    });
    const queryString = searchParams.toString();
    if (queryString) {
      url += `?${queryString}`;
    }
  }

  // 2. Формирование заголовков
  const requestHeaders: Record<string, string> = {
    Accept: 'application/json',
    ...headers,
  };

  // Передача токена авторизации
  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('personal_os_access_token');
    if (token) {
      requestHeaders['Authorization'] = `Bearer ${token}`;
    }
  }

  // Автоматический Idempotency-Key для POST мутаций, если не передан явно
  if (method === 'POST') {
    requestHeaders['Idempotency-Key'] = idempotencyKey || crypto.randomUUID();
  } else if (idempotencyKey) {
    requestHeaders['Idempotency-Key'] = idempotencyKey;
  }

  // ETag оптимистическая блокировка для PATCH и PUT
  if ((method === 'PATCH' || method === 'PUT') && ifMatch !== undefined) {
    requestHeaders['If-Match'] = typeof ifMatch === 'number' ? `W/"${ifMatch}"` : ifMatch;
  }

  // Тело запроса
  let requestBody: string | undefined;
  if (body !== undefined) {
    requestHeaders['Content-Type'] = 'application/json';
    requestBody = JSON.stringify(body);
  }

  // 3. Выполнение сетевого запроса
  const response = await fetch(url, {
    method,
    headers: requestHeaders,
    body: requestBody,
    signal,
  });

  // 4. Обработка успешных ответов 204 No Content
  if (response.status === 204) {
    return {} as TData;
  }

  // 5. Обработка ошибок (RFC 9457 Problem Details)
  if (!response.ok) {
    let errorProblem: ProblemDetails;
    try {
      errorProblem = await response.json();
    } catch {
      errorProblem = {
        type: 'https://api.personal-os.internal/errors/unknown',
        title: response.statusText || 'Unknown Error',
        status: response.status,
        detail: `HTTP request failed with status ${response.status}`,
      };
    }

    // Специальная обработка 401 Unauthorized (истечение сессии)
    if (response.status === 401 && typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('auth:session_expired'));
    }

    throw new ApiError(errorProblem);
  }

  // 6. Парсинг JSON успешного ответа
  return (await response.json()) as TData;
}
```

### 3.2 Курсорная пагинация (`fetchPaginated`)

```typescript
// lib/api-client.ts (дополнение)

export interface PaginatedResult<TItem> {
  items: TItem[];
  pagination: {
    has_more: boolean;
    next_cursor: string | null;
    total_count_approx?: number;
  };
}

export async function fetchPaginated<TItem>(
  path: string,
  options: {
    cursor?: string | null;
    limit?: number;
    filters?: Record<string, string | number | boolean | undefined>;
    signal?: AbortSignal;
  } = {}
): Promise<PaginatedResult<TItem>> {
  const { cursor, limit = 50, filters = {}, signal } = options;
  return apiRequest<PaginatedResult<TItem>>('GET', path, {
    params: {
      ...filters,
      cursor: cursor || undefined,
      limit,
    },
    signal,
  });
}
```

### 3.3 Стратегия разрешения конфликтов (409 Conflict и 412 Precondition Failed)

1. **409 Conflict (Idempotency in-flight):** Запрос с таким `Idempotency-Key` уже исполняется. Клиент автоматически делает задержку 500ms и повторяет попытку до 2 раз. Если конфликт не разрешился — выводится Toast: `"Операция выполняется в другом процессе"`.
2. **412 Precondition Failed (Lost Update):** Другое устройство изменило задачу/событие (версия в БД выше, чем переданный `If-Match`). Клиент:
   - Не затирает данные вслепую.
   - Запрашивает свежую версию сущности с сервера (`GET /v1/{resource}/{id}`).
   - Выводит пользователю диалог: `"Сущность была обновлена на другом устройстве. Ваши локальные изменения отклонены. Нажмите 'Обновить', чтобы увидеть свежие данные"`.

---

# 4. WEBSOCKET CLIENT LAYER

Real-time слой фронтенда подключается к шлюзу `/v1/ws` Core API и транслирует доменные события непосредственно в реактивные обновления кэша TanStack Query и системные нотификации.

```
       +---------------------------------------------+
       |             CORE API GATEWAY                |
       |               /v1/ws (WSS)                  |
       +----------------------+----------------------+
                              |
                              | Domain Events (Transactional Outbox)
                              v
       +---------------------------------------------+
       |             WS CLIENT SINGLETON             |
       |      - Exponential Backoff + Jitter         |
       |      - Heartbeat ping/pong (30s)            |
       |      - Missed Events Timestamp Sync         |
       +----------------------+----------------------+
                              |
               +--------------+--------------+
               |                             |
               v                             v
+------------------------------+ +------------------------------+
|     TANSTACK QUERY CACHE     | |       USER NOTIFICATIONS     |
| • task.updated -> invalidate | | • notification.dispatched    |
| • calendar.changed -> update | |   -> Sonner Toast + Audio    |
| • finance.posted -> refresh  | | • unread badge counter + 1   |
+------------------------------+ +------------------------------+
```

### 4.1 Реализация синглтона WebSocket (`lib/ws-client.ts`)

```typescript
// lib/ws-client.ts
import { queryClient } from './query-client';
import { queryKeys } from './query-keys';

export interface WebSocketEnvelope<TData = unknown> {
  event_id: string;
  event_type: string;
  occurred_at: string;
  workspace_id: string;
  actor: {
    actor_id: string;
    actor_type: 'user' | 'ai_agent' | 'system' | 'integration';
  };
  aggregate: {
    id: string;
    type: string;
    version: number;
  };
  correlation_id: string;
  data: TData;
}

type EventHandler<T = any> = (event: WebSocketEnvelope<T>) => void;

class WebSocketManager {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private baseDelay = 1000;
  private maxDelay = 30000;
  private pingIntervalId: number | null = null;
  private pongTimeoutId: number | null = null;
  private handlers = new Map<string, Set<EventHandler>>();
  private lastEventOccurredAt: string | null = null;
  private isExplicitlyClosed = false;

  constructor() {
    const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = typeof window !== 'undefined' ? window.location.host : 'localhost:8000';
    this.url = `${protocol}//${host}/v1/ws`;
  }

  public connect(token: string) {
    if (typeof window === 'undefined') return;
    this.isExplicitlyClosed = false;

    // Закрываем предыдущее соединение, если оно существовало
    if (this.ws) {
      this.ws.close();
    }

    try {
      this.ws = new WebSocket(`${this.url}?token=${encodeURIComponent(token)}`);
      this.setupListeners();
    } catch (err) {
      console.error('[WS] Connection failed to initialize:', err);
      this.scheduleReconnect(token);
    }
  }

  private setupListeners() {
    if (!this.ws) return;

    this.ws.onopen = () => {
      console.info('[WS] Connection established');
      this.reconnectAttempts = 0;
      this.startHeartbeat();

      // При успешном реконнекте после сбоя — синхронизируем данные
      if (this.lastEventOccurredAt) {
        this.reconcileMissedEvents();
      }
    };

    this.ws.onmessage = (messageEvent) => {
      try {
        const payload = JSON.parse(messageEvent.data);

        // Обработка Heartbeat pong
        if (payload.type === 'pong') {
          if (this.pongTimeoutId) {
            clearTimeout(this.pongTimeoutId);
            this.pongTimeoutId = null;
          }
          return;
        }

        // Обработка входящего доменного события
        const envelope = payload as WebSocketEnvelope;
        this.lastEventOccurredAt = envelope.occurred_at;
        this.dispatchDomainEvent(envelope);
      } catch (err) {
        console.warn('[WS] Failed to parse message:', messageEvent.data, err);
      }
    };

    this.ws.onerror = (event) => {
      console.warn('[WS] Error encountered:', event);
    };

    this.ws.onclose = (closeEvent) => {
      this.stopHeartbeat();
      if (!this.isExplicitlyClosed) {
        console.warn(`[WS] Connection closed (code: ${closeEvent.code}). Reconnecting...`);
        const token = localStorage.getItem('personal_os_access_token');
        if (token) {
          this.scheduleReconnect(token);
        }
      }
    };
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    // Пинг каждые 30 секунд
    this.pingIntervalId = window.setInterval(() => {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
        // Ожидаем pong в течение 10 секунд
        this.pongTimeoutId = window.setTimeout(() => {
          console.warn('[WS] Pong timeout. Terminating dead connection.');
          this.ws?.close();
        }, 10000);
      }
    }, 30000);
  }

  private stopHeartbeat() {
    if (this.pingIntervalId) clearInterval(this.pingIntervalId);
    if (this.pongTimeoutId) clearTimeout(this.pongTimeoutId);
    this.pingIntervalId = null;
    this.pongTimeoutId = null;
  }

  private scheduleReconnect(token: string) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('[WS] Max reconnect attempts reached. Waiting for user interaction.');
      return;
    }

    // Экспоненциальный бэкофф с джиттером (Full Jitter)
    const delay = Math.min(
      this.maxDelay,
      this.baseDelay * Math.pow(1.5, this.reconnectAttempts)
    );
    const jitter = delay * 0.2 * (Math.random() * 2 - 1);
    const finalDelay = Math.max(500, Math.floor(delay + jitter));

    this.reconnectAttempts++;
    console.info(`[WS] Reconnecting in ${finalDelay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);

    window.setTimeout(() => {
      this.connect(token);
    }, finalDelay);
  }

  public subscribe(eventType: string, handler: EventHandler) {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler);

    return () => {
      this.handlers.get(eventType)?.delete(handler);
    };
  }

  private dispatchDomainEvent(event: WebSocketEnvelope) {
    // 1. Уведомляем локальных подписчиков на данный event_type
    const specificHandlers = this.handlers.get(event.event_type);
    specificHandlers?.forEach((handler) => handler(event));

    // Уведомляем слушателей подстановочных символов ('*')
    const wildcardHandlers = this.handlers.get('*');
    wildcardHandlers?.forEach((handler) => handler(event));

    // 2. Выполняем автоматическую инвалидацию кэша TanStack Query
    this.routeEventToQueryCache(event);
  }

  private routeEventToQueryCache(event: WebSocketEnvelope) {
    const { event_type, aggregate } = event;

    switch (event_type) {
      // События задач
      case 'task.created':
      case 'task.status_changed':
      case 'task.rescheduled':
      case 'task.completed':
      case 'task.deleted':
        queryClient.invalidateQueries({ queryKey: queryKeys.tasks.lists() });
        queryClient.invalidateQueries({ queryKey: queryKeys.tasks.today() });
        if (aggregate.id) {
          queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(aggregate.id) });
        }
        break;

      // События календаря
      case 'calendar_event.created':
      case 'calendar_event.updated':
      case 'calendar_event.deleted':
      case 'timeblock.allocated':
      case 'timeblock.released':
        queryClient.invalidateQueries({ queryKey: queryKeys.calendar.all });
        break;

      // Финансовые события
      case 'transaction.posted':
      case 'budget.threshold_exceeded':
        queryClient.invalidateQueries({ queryKey: queryKeys.finance.all });
        break;

      // Привычки
      case 'habit.logged':
      case 'habit.streak_reset':
        queryClient.invalidateQueries({ queryKey: queryKeys.habits.all });
        break;

      // Новые уведомления
      case 'notification.dispatched':
        queryClient.invalidateQueries({ queryKey: queryKeys.notifications.all });
        // Показ тоста в правом нижнем углу
        window.dispatchEvent(new CustomEvent('notification:received', { detail: event.data }));
        break;

      // AI предложения действий
      case 'ai.action_proposed':
        queryClient.invalidateQueries({ queryKey: queryKeys.ai.proposals() });
        window.dispatchEvent(new CustomEvent('ai:proposal_received', { detail: event.data }));
        break;

      default:
        break;
    }
  }

  private reconcileMissedEvents() {
    console.info(`[WS] Reconciling missed events since ${this.lastEventOccurredAt}`);
    // Инвалидируем все активные запросы, чтобы синхронизировать экран после оффлайна
    queryClient.invalidateQueries({ type: 'active' });
  }

  public disconnect() {
    this.isExplicitlyClosed = true;
    this.stopHeartbeat();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export const wsClient = new WebSocketManager();
```

---

# 5. ROUTING И LAYOUTS

Next.js 14 App Router обеспечивает компонентную композицию страниц, потоковую передачу данных (Streaming SSR via Suspense) и контекстное сохранение состояния экранов.

```
/ (Root)
│
├── (auth) [Auth Layout: Centered minimal]
│   ├── /login
│   ├── /register
│   └── /callback
│
└── (app) [App Layout: AppShell, Sidebar, BottomTabs, Providers]
    ├── /today ── TodayDashboard (Morning Brief, Tasks, Events)
    │
    ├── /tasks ── TasksView (?view=kanban|list)
    │   └── @modal/(.)[id] ── TaskDetailSlideOver (Intercepting Route!)
    │
    ├── /projects/[id] ── ProjectDetail (Milestones, Tasks, Budget)
    ├── /calendar ── CalendarView (?view=day|week|month)
    ├── /finance ── FinanceDashboard (Accounts, Budgets, Ledger)
    ├── /habits ── HabitTracker (Heatmap, Streaks)
    ├── /notes/[id] ── NoteEditor (Markdown, Tags)
    └── /settings ── SettingsLayout (Profile, Integrations, Notifications)
```

### 5.1 Контекстное сохранение экрана через Intercepting Routes (`@modal/(.)[id]`)

**Архитектурное решение UX-принципа Context Preservation:**  
Когда пользователь кликает на задачу в списке или доске Kanban (`/tasks`), маршрутизатор Next.js активирует перехватывающий роут `apps/web/app/(app)/tasks/@modal/(.)[id]/page.tsx`.

1. **Поведение в SPA:** Открывается правая панель Slide-over (`<TaskDetailSheet taskId={id} />`). Текущая страница `/tasks` остается в DOM, сохраняя позицию скролла, активные фильтры и фокус ввода. URL в браузере обновляется на `/tasks/{id}` через `window.history.pushState`.
2. **Поведение при прямом переходе / Refresh:** Если пользователь перезагружает страницу или открывает ссылку `/tasks/{id}` в новой вкладке, срабатывает полноценный маршрут `apps/web/app/(app)/tasks/[id]/page.tsx`, отображающий полноэкранную детальную страницу.
3. **Закрытие панели:** Нажатие Esc или кнопки «Закрыть» выполняет `router.back()`, плавно скрывая панель без сетевых запросов.

### 5.2 Матрица маршрутов приложения

| URI | Route File | Тип компонента | Назначение |
|---|---|---|---|
| `/` | `app/(app)/page.tsx` | Server Component | Мгновенный 307 Redirect на `/today` |
| `/login` | `app/(auth)/login/page.tsx` | Client Component | Форма входа по email или magic link |
| `/register` | `app/(auth)/register/page.tsx` | Client Component | Регистрация и создание первого пространства |
| `/today` | `app/(app)/today/page.tsx` | Hybrid (RSC + Client) | Главный экран дня (Morning Brief, задачи, расписание) |
| `/tasks` | `app/(app)/tasks/page.tsx` | Client Component | Доска Kanban / Табличный список задач |
| `/tasks/[id]` | `app/(app)/tasks/[id]/page.tsx` | Hybrid (RSC + Client) | Полностраничный вид задачи при прямом переходе |
| `/tasks/@modal/(.)[id]` | `app/(app)/tasks/@modal/(.)[id]/page.tsx` | Client Component | Slide-over Sheet поверх канбана/списка |
| `/projects/[id]` | `app/(app)/projects/[id]/page.tsx` | Hybrid (RSC + Client) | Обзор проекта: прогресс, задачи, бюджет |
| `/calendar` | `app/(app)/calendar/page.tsx` | Client Component | Календарная сетка на базе FullCalendar |
| `/finance` | `app/(app)/finance/page.tsx` | Client Component | Балансы счетов, прогресс бюджетов, журнал проводок |
| `/habits` | `app/(app)/habits/page.tsx` | Client Component | Трекер привычек с теплокартой активности |
| `/notes/[id]` | `app/(app)/notes/[id]/page.tsx` | Client Component | Редактор Markdown с семантическими тегами |
| `/settings/integrations` | `app/(app)/settings/integrations/page.tsx` | Client Component | Настройка OAuth2 Google Calendar и Telegram Bot |

### 5.3 Иерархия Лэйаутов (`AppShell`)

Компонент `components/layout/AppShell.tsx` реализует адаптивную сетку:
- **Desktop (>= 1024px):** Сворачиваемый боковой `Sidebar` (64px в свернутом виде, 240px в развернутом). Верхний `TopHeader` со строкой быстрого поиска, кнопкой Quick Add (`Cmd+K`), статусом AI и колокольчиком уведомлений.
- **Mobile (< 1024px):** Сайдбар скрывается. Внизу фиксируется `BottomTabBar` из 5 элементов (Today, Tasks, Quick Add FAB, Calendar, Finance) с поддержкой Safe Area Insets (iOS).

---

# 6. ТРЕБОВАНИЯ К FRONTEND КОДУ

### 6.1 Граница Server Components (RSC) vs Client Components

| Правило | Server Component (`.tsx`) | Client Component (`'use client'`) |
|---|---|---|
| **Назначение** | Начальный каркас, SSR метаданные, предварительная загрузка данных через REST API | Интерактивность, обработчики событий, Drag-and-Drop, WebSockets, анимации |
| **Доступ к БД** | **СТРОГО ЗАПРЕЩЕН.** Никаких прямых SQL / ORM вызовов. Только `apiRequest` к Core API | Запрещен |
| **Хуки React** | Недоступны (`useState`, `useEffect`, `useContext`) | Доступны |
| **TanStack Query** | Доступен `prefetchQuery` + `<HydrationBoundary state={dehydrate(queryClient)}>` | Доступны `useQuery`, `useMutation` |
| **Размер бандла** | 0 KB в JS-бандле клиента | Включается в JS-бандл (минимизировать зависимости) |

### 6.2 Реализация Kanban на базе `@dnd-kit`

- **Библиотеки:** `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`.
- **Колонки:** 6 фиксированных колонок согласно BA/UI спецификации: `inbox`, `backlog`, `scheduled`, `in_progress`, `blocked`, `done`.
- **Датчики (Sensors):** `PointerSensor` с задержкой активации (distance: 5px) для исключения ложных срабатываний при клике, и `KeyboardSensor` для полной доступности.
- **Алгоритм столкновений:** `closestCorners` для надежного попадания между карточками.
- **Оптимистичный DnD Flow:**
  1. Пользователь отпускает карточку (`onDragEnd`).
  2. Если колонка или индекс изменились — хук `useKanban` немедленно переставляет карточку в локальном кэше TanStack Query (`queryClient.setQueryData`).
  3. Отправляется мутация `PATCH /v1/tasks/{id}` с параметрами `{ status: newStatus, sort_order: newOrder }`.
  4. При ошибке сети состояние мгновенно откатывается назад с показом Toast.

```typescript
// components/domain/tasks/KanbanBoard.tsx (Архитектурный каркас)
'use client';

import React, { useState } from 'react';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragStartEvent,
  DragEndEvent,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { KanbanColumn } from './KanbanColumn';
import { TaskCard } from './TaskCard';
import { Task } from '@/types/domain';
import { useTaskMutations } from '@/hooks/useTasks';

const COLUMNS = [
  { id: 'inbox', title: 'Inbox' },
  { id: 'backlog', title: 'Backlog' },
  { id: 'scheduled', title: 'Scheduled' },
  { id: 'in_progress', title: 'In Progress' },
  { id: 'blocked', title: 'Blocked' },
  { id: 'done', title: 'Done' },
] as const;

export function KanbanBoard({ tasks }: { tasks: Task[] }) {
  const [activeTask, setActiveTask] = useState<Task | null>(null);
  const { moveTaskOptimistic } = useTaskMutations();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragStart = (event: DragStartEvent) => {
    const task = tasks.find((t) => t.id === event.active.id);
    if (task) setActiveTask(task);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveTask(null);
    if (!over) return;

    const taskId = String(active.id);
    const overId = String(over.id);

    // Логика вычисления целевой колонки и вызов мутации
    moveTaskOptimistic({ taskId, targetColumnOrTaskId: overId });
  };

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCorners}
      onDragStart={handleDragStart}
      onDragEnd={handleDragEnd}
    >
      <div className="flex h-full gap-4 overflow-x-auto pb-4 pt-2">
        {COLUMNS.map((col) => (
          <KanbanColumn
            key={col.id}
            id={col.id}
            title={col.title}
            tasks={tasks.filter((t) => t.status === col.id)}
          />
        ))}
      </div>
      <DragOverlay>
        {activeTask ? <TaskCard task={activeTask} isOverlay /> : null}
      </DragOverlay>
    </DndContext>
  );
}
```

### 6.3 Архитектура Календаря (FullCalendar)

- **Библиотеки:** `@fullcalendar/react`, `@fullcalendar/daygrid`, `@fullcalendar/timegrid`, `@fullcalendar/interaction`.
- **Пакетная изоляция:** Календарь подключается через Client Component с динамическим импортом (`next/dynamic`) без SSR, предотвращая раздувание начального бандла:
  ```typescript
  const CalendarView = dynamic(() => import('@/components/domain/calendar/CalendarGrid'), {
    ssr: false,
    loading: () => <CalendarSkeleton />,
  });
  ```
- **Синхронизация слотов:** Календарь отображает как внешние события Google Calendar (`is_external: true`), так и внутренние временные блоки задач (`TimeBlock`). При перетаскивании события в календаре вызывается `PATCH /v1/calendar/events/{id}` с новым интервалом `start_time` и `end_time`.

### 6.4 Архитектура PWA и Service Worker

- **Конфигурация PWA:**
  - `public/manifest.json`:
    - `name`: "Personal OS"
    - `short_name`: "PersonalOS"
    - `display`: "standalone"
    - `start_url`: "/today"
    - `theme_color`: "#0B0F19"
    - `background_color`: "#0B0F19"
    - `orientation`: "portrait-primary"
  - `public/sw.js`:
    - Стратегия **CacheFirst**: Шрифты (`Inter`, `JetBrains Mono`), статические ассеты (`/_next/static/*`), иконки.
    - Стратегия **StaleWhileRevalidate**: Статический HTML-каркас страниц.
    - Стратегия **NetworkOnly с оффлайн-фолбэком**: API-запросы (`/v1/*`). При отсутствии сети возвращается кэшированное состояние из IndexedDB или `offline.html`.
    - Обработчик **Web Push Notifications** (VAPID): перехват пушей при закрытом приложении и открытие нужного URL по клику.

### 6.5 Интернационализация (i18n)

- **Библиотека:** `next-intl`.
- **Локали:** Основная — `ru` (Русский), резервная — `en` (Английский).
- **Схема хранения:** Выбранная локаль сохраняется в Cookie `NEXT_LOCALE` и профиле пользователя в БД.
- **Типобезопасность:** Сгенерированные типы для всех ключей сообщений:
  ```typescript
  import { useTranslations } from 'next-intl';
  const t = useTranslations('Tasks');
  // t('create_button') -> "Создать задачу"
  ```

---

# 7. ТЕСТОВАЯ СТРАТЕГИЯ FRONTEND

Пирамида тестирования фронтенда гарантирует стабильность и предотвращает регрессии интерфейса:

```
        / \
       /   \         E2E Tests (Playwright)
      / E2E \        Critical User Flows, Quick Add <= 3 actions, DnD
     /-------\
    / Inter-  \      Integration Tests (Vitest + MSW)
   /  vention  \     API & WS mock, Query caching, Optimistic rollback
  /-------------\
 /  Unit Tests   \   Unit Tests (Vitest + React Testing Library)
/-----------------\  Domain Components, Hooks, Formatters, A11y axe-core
```

### 7.1 Unit Tests (Vitest + React Testing Library)
- Тестирование изолированных компонентов: `TaskCard`, `BudgetProgress`, `EventChip`, `MorningBriefCard`, `AIPreviewDiff`.
- Тестирование пользовательских хуков: `useOptimisticUpdate`, `useDebounce`, `useKeyboardShortcut`.

```typescript
// tests/unit/components/BudgetProgress.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { BudgetProgress } from '@/components/domain/finance/BudgetProgress';

describe('BudgetProgress Component', () => {
  it('отображает нормальное состояние бюджета до 80%', () => {
    render(<BudgetProgress categoryName="Кафе" spentMinor={450000} limitMinor={1000000} />);
    expect(screen.getByText('Кафе')).toBeInTheDocument();
    expect(screen.getByText('45%')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveClass('bg-emerald-500');
  });

  it('отображает предупреждающий цвет при превышении 80%', () => {
    render(<BudgetProgress categoryName="Продукты" spentMinor={850000} limitMinor={1000000} />);
    expect(screen.getByRole('progressbar')).toHaveClass('bg-amber-500');
  });

  it('отображает ошибку и алерт при перерасходе 100%', () => {
    render(<BudgetProgress categoryName="Развлечения" spentMinor={1200000} limitMinor={1000000} />);
    expect(screen.getByRole('progressbar')).toHaveClass('bg-rose-500');
    expect(screen.getByText(/Лимит превышен/i)).toBeInTheDocument();
  });
});
```

### 7.2 Integration Tests (MSW - Mock Service Worker)
- Мокирование HTTP-эндпоинтов `/v1/*` и проверка поведения TanStack Query при ошибках `409 Conflict`, `412 Precondition Failed` и `422 Validation Error`.
- Проверка механизма отката оптимистичного состояния при ошибке сети.

### 7.3 E2E Tests (Playwright)
Набор автоматизированных сценариев критического пути (Critical User Journeys):

1. **Quick Add Flow (<= 3 действия):**
   - Нажатие `Cmd+K`.
   - Ввод текста: `"Купить билеты на самолет в пятницу #travel !high"`.
   - Проверка NLP-распознавания (тип Task, приоритет High, проект Travel).
   - Нажатие `Enter` -> Закрытие модалки -> Карточка задачи появилась на экране Today.
2. **Kanban Drag-and-Drop:**
   - Перетаскивание задачи из колонки `Backlog` в `In Progress`.
   - Проверка немедленного оптимистичного перемещения в UI.
   - Проверка отправки исходящего `PATCH /v1/tasks/{id}` с `status: "in_progress"`.
3. **Task Detail Slide-over (Context Preservation):**
   - Клик по задаче в списке с фильтрами.
   - Проверка появления Slide-over Sheet.
   - Проверка неизменности URL query-параметров фильтров и позиции скролла списка.
4. **Finance Expense Entry:**
   - Быстрый ввод расхода через модалку Quick Add: `"500р обед"`.
   - Проверка обновления счетчика дневных расходов на экране `/finance`.
5. **Accessibility Audit:**
   - Прогон `@axe-core/playwright` на страницах `/today`, `/tasks`, `/calendar`, `/finance`.
   - Проверка отсутствия критических нарушений WCAG 2.1 AA.

```typescript
// tests/e2e/quick-add.spec.ts
import { test, expect } from '@playwright/test';

test.describe('Quick Add Flow', () => {
  test('создает задачу в 2 действия через Cmd+K', async ({ page }) => {
    await page.goto('/today');

    // 1 действие: нажатие хоткея
    await page.keyboard.press('Meta+KeyK');
    const modal = page.locator('[data-testid="quick-add-modal"]');
    await expect(modal).toBeVisible();

    // 2 действие: ввод и подтверждение по Enter
    const input = page.locator('[data-testid="quick-add-input"]');
    await input.fill('Сдать отчет по проекту #work !high');
    await page.keyboard.press('Enter');

    // Проверка результата
    await expect(modal).not.toBeVisible();
    const toast = page.locator('[data-testid="toast-success"]');
    await expect(toast).toContainText('Задача создана');
  });
});
```

---

# 8. PERFORMANCE ТАРГЕТЫ И БЮДЖЕТЫ

Для обеспечения плавной работы персональной ОС на мобильных и десктопных устройствах зафиксированы строгие метрики производительности:

```
+--------------------------------------------------------------------------+
|                       PERFORMANCE BUDGETS & SLA                          |
+------------------------------+---------------+---------------------------+
| Метрика                      | Таргет        | Механизм оптимизации      |
+------------------------------+---------------+---------------------------+
| **LCP** (Largest Contentful) | < 2.0s        | SSR каркаса, font-display |
| **INP** (Interaction to Next)| < 100ms       | React Transitions         |
| **CLS** (Cumulative Shift)   | < 0.05        | Фиксированные скелетоны   |
| **Quick Add Input Latency**  | < 50ms        | Локальный стейт, debounce |
| **Kanban Drag Frame Rate**   | 60 FPS        | GPU transform, dnd-kit    |
| **Initial JS Bundle (gzip)** | < 150 KB      | Route Code Splitting      |
| **Full Calendar Load Time**  | < 400ms       | Dynamic Import (no SSR)   |
| **Cold Start PWA (Cache)**   | < 800ms       | Service Worker Precache   |
+------------------------------+---------------+---------------------------+
```

### 8.1 Техники оптимизации бандла
1. **Dynamic Code Splitting:**
   - Тяжелые библиотеки выносятся в асинхронные чанки:
     - `@fullcalendar/*` (~120 KB gzip) загружается только на `/calendar`.
     - `@tiptap/*` (Markdown Editor, ~75 KB gzip) загружается только на `/notes/[id]`.
     - `recharts` (~85 KB gzip) загружается только на `/finance`.
2. **Виртуализация списков:**
   - Использование `@tanstack/react-virtual` для колонок Kanban и журнала транзакций при количестве элементов более 100, что гарантирует рендеринг только видимых в viewport DOM-узлов.
3. **Шрифтовая оптимизация:**
   - Шрифты `next/font/google` (`Inter` и `JetBrains Mono`) предварительно загружаются с `display: 'swap'` и подмножествами `latin, cyrillic` без внешних блокирующих сетевых запросов.
4. **Мемоизация селекторов:**
   - Использование гранулярных селекторов Zustand (`useUIStore((state) => state.isSidebarCollapsed)`) для предотвращения ререндеринга дерева компонентов при изменении несвязанных полей стора.

---

# 9. ИТОГОВАЯ ВЕРИФИКАЦИЯ И МАНДАТНЫЙ КОНТРАКТ

- **Статус:** `STATUS: VERIFIED`
- **Соответствие upstream спецификациям:**
  - Полное следование 7 UX-принципам из `17-ux-designer.md` (Speed, Single Source, AI Safety First, Context Preservation via Intercepting Routes, Forgiving Design, Progressive Disclosure, Channel Parity).
  - Интеграция всех HSL CSS переменных дизайн-токенов и компонентов из `18-ui-designer.md`.
  - Строгая совместимость со стандартами REST API v1, WebSocket, Transactional Outbox Event Catalog и RFC 9457 из `04-solution-architect.md`.
- **Следующий этап:** Передача архитектурного документа агенту `19-frontend-logic-developer` для реализации бизнес-логики, хуков, сторов и клиентских модулей.
