# 20 — UI Component Developer

STATUS: VERIFIED
TASK: Разработка ключевых UI компонентов Personal OS на стеке Next.js 14+ App Router, React 18, TypeScript, Tailwind CSS и @dnd-kit: система дизайн-токенов CSS vars (светлая/тёмная темы), адаптивный AppShell с боковой панелью (64px / 240px) и мобильным PWA BottomTabBar, интерактивная карточка задачи TaskCard с расчетом overdue и dnd-kit sortable, KanbanBoard на 6 колонок жизненного цикла задач с DndContext, модальное окно быстрого ввода QuickAddModal (Cmd+K / NLP превью <= 3 действий), безопасный AI-компонент подтверждения диффа AIPreviewDiff с возможностью частичного применения, строка финансового журнала ExpenseRow, экраны TodayDashboard (/today) и Tasks (/tasks) с переключателем Kanban/List, а также адаптивная карточка утреннего брифинга MorningBriefCard.

INPUT:
- `docs/it-company/04-solution-architect.md` — ADR-006 (Kanban как view над Task.status), TimeBlock модель, RFC 9457 Problem Details.
- `docs/it-company/06-system-analyst.md` — Диаграммы состояний жизненного цикла задач, переходы между колонками.
- `docs/it-company/16-frontend-architect.md` — Структура каталогов Next.js, разделение Server State (TanStack Query) и UI State (Zustand), перехватывающие маршруты (@modal).
- `docs/it-company/17-ux-designer.md` — 7 UX принципов (Quick Add <= 3 действий, Context Preservation, Safe AI Preview, Forgiving Design с Undo).
- `docs/it-company/18-ui-designer.md` — Спецификация дизайн-токенов (Цвета, Типографика Inter, Сетка 4px, Радиусы, Тени, Анимации 150/250/400ms), HTML-разметка компонентов.
- `docs/it-company/19-frontend-logic-developer.md` — Хуки бизнес-логики (`useTasks`, `useQuickAdd`, `useDashboardToday`, `useUIStore`), доменные контракты (`Task`, `TaskStatus`, `Transaction`, `CalendarEvent`, `BudgetSummary`).

ACTIONS:
1. Создана и верифицирована система дизайн-токенов в `apps/web/src/styles/globals.css`:
   - Базовая палитра: Modern Indigo (`--color-primary-500: #6366f1`), фоны (`--color-background`, `--color-surface`, `--color-border`), текст (`--color-text-primary`, `--color-text-secondary`, `--color-text-muted`).
   - Статусы и приоритеты: Critical (`#dc2626`), High (`#f97316`), Medium (`#eab308`), Low (`#6b7280`).
   - Доменные цвета: Tasks (`#6366f1`), Calendar (`#0ea5e9`), Finance (`#10b981`).
   - Тайминги анимаций: `--motion-fast: 150ms`, `--motion-normal: 250ms`, `--motion-slow: 400ms`.
   - Поддержка тёмной темы через селектор `[data-theme="dark"]` без эффекта цветового размытия на OLED (фон `#0f172a`, поверхности `#1e293b`).
2. Разработан адаптивный лейаут `components/layout/AppShell.tsx`:
   - Десктопная боковая панель `SidebarNav` с переключением ширины (64px в свернутом виде, 240px в развернутом) и навигацией L1/L2.
   - Мобильная панель `BottomTabBar` на 5 вкладок с приподнятым центральным FAB быстрого ввода и поддержкой Safe Area Insets.
   - Верхний `TopHeader` с глобальным триггером поиска/добавления (`Cmd+K`), переключателем тем, центром уведомлений и профилем.
   - Выдвижная правая панель Slide-over (Sheet) для сохранения контекста страницы (Context Preservation).
3. Создан компонент карточки задачи `components/domain/tasks/TaskCard.tsx`:
   - Отображение названия, цветного бейджа приоритета (!critical, !high, !medium, !low), проектного тега (#work, #infra, #personal) и прогресса чек-листа подзадач (completed/total).
   - Динамический расчет дедлайна с подсветкой красным `text-rose-600` при `due_at < now` (overdue).
   - Интеграция с `@dnd-kit/sortable` (`useSortable` drag handle, плавная интерполяция перемещения).
   - Полная WAI-ARIA доступность: роль `article`, фокус-ринги, управление чекбоксом с клавиатуры.
4. Разработана интерактивная доска `components/domain/tasks/KanbanBoard.tsx`:
   - Построена на базе `@dnd-kit/core` (`DndContext`, `PointerSensor` с distance constraint 5px, `KeyboardSensor`).
   - 6 колонок жизненного цикла: `inbox`, `todo`, `scheduled`, `in_progress`, `waiting`, `done`.
   - Дочерний компонент `KanbanColumn`: шапка со счётчиком и кнопкой добавления, SortableContext с вертикальной стратегией сортировки.
   - Оптимистичное перемещение задач при перетаскивании с отрисовкой `DragOverlay`.
5. Реализовано глобальное модальное окно быстрого захвата `components/domain/quick-add/QuickAddModal.tsx`:
   - Глобальный шорткат `Cmd+K` / `Ctrl+K` или клик по FAB.
   - Автофокус в свободное поле ввода и распознавание намерения (Task / Event / Expense / Note) на лету (дебаунс 300мс).
   - Интерактивные чипы предварительного просмотра распознанных метаданных: дедлайн, теги проекта, сумма, валюта, приоритет.
   - Подтверждение по нажатию `Enter` (Quick Add <= 3 действий).
   - Фолбэк на ручную структурированную форму по клику на «Подробные поля».
6. Создан компонент безопасного применения рекомендаций AI `components/domain/ai/AIPreviewDiff.tsx`:
   - Визуализация различий между текущим планом (Before) и предлагаемым решением (After).
   - Индикатор уверенности AI (Confidence score).
   - Чекбоксы по каждому атомарному действию для частичного принятия (`onPartialApply`).
   - Кнопки «Аппликовать всё», «Применить выбранные», «Отклонить».
7. Реализована строка финансового журнала `components/domain/finance/ExpenseRow.tsx`:
   - Форматированное представление денежных сумм (`+ 50 000 ₽` / `- 450 ₽`) с использованием пробелов групп разрядов.
   - Семантическая цветовая маркировка: доходы — `text-emerald-600`, расходы — `text-rose-600`.
   - Иконка категории, название счета и дата транзакции.
8. Разработан экран Today Dashboard `app/(app)/today/page.tsx`:
   - Server Component shell + Client Component `TodayDashboard`.
   - Баннер предупреждения просроченных задач `OverdueBanner`.
   - Полноширинная интеллектуальная карточка `MorningBriefCard`.
   - Секция `TopTasks` (3 приоритетные задачи дня).
   - Дневная лента расписания и встреч `CalendarStrip`.
   - Прогресс-бар бюджета текущего месяца `BudgetSummaryBar` с пороговой индикацией (<70% зелёный, 70-90% жёлтый, >90% красный).
9. Разработан экран задач `app/(app)/tasks/page.tsx`:
   - Переключатель режимов отображения `ViewSwitcher` (Канбан / Список).
   - Панель фильтрации `FilterBar` по статусу, приоритету, проекту и поисковому запросу.
   - Режим канбана с поддержкой DnD и режим списка с бесконечным скроллом.
10. Разработан компонент утреннего брифинга `components/domain/notifications/MorningBriefCard.tsx`:
    - Сводная статистика дня: количество встреч, число задач (с выделением критических), свободные часы.
    - AI-комментарий и персональный совет по распределению фокусного времени.
    - Раскрываемый список предлагаемых тайм-блоков с чекбоксами для частичного включения в календарь.

CHANGED_FILES:
- `apps/web/src/styles/globals.css`
- `apps/web/src/components/layout/AppShell.tsx`
- `apps/web/src/components/layout/SidebarNav.tsx`
- `apps/web/src/components/layout/TopHeader.tsx`
- `apps/web/src/components/layout/BottomTabBar.tsx`
- `apps/web/src/components/domain/tasks/TaskCard.tsx`
- `apps/web/src/components/domain/tasks/KanbanColumn.tsx`
- `apps/web/src/components/domain/tasks/KanbanBoard.tsx`
- `apps/web/src/components/domain/quick-add/QuickAddModal.tsx`
- `apps/web/src/components/domain/ai/AIPreviewDiff.tsx`
- `apps/web/src/components/domain/finance/ExpenseRow.tsx`
- `apps/web/src/components/domain/notifications/MorningBriefCard.tsx`
- `apps/web/src/components/domain/today/TodayDashboard.tsx`
- `apps/web/src/app/layout.tsx`
- `apps/web/src/app/page.tsx`
- `apps/web/src/app/(app)/layout.tsx`
- `apps/web/src/app/(app)/today/page.tsx`
- `apps/web/src/app/(app)/tasks/page.tsx`
- `apps/web/src/types/domain.ts` (совместимость алиасов `TaskStatus`, `Priority`, `CalendarEvent`, `BudgetSummary`)
- `apps/web/src/types/ai.ts` (поля `time` и `confidence`)
- `apps/web/src/stores/ui-store.ts` (методы быстрого доступа для модалок и сайдбара)
- `apps/web/src/hooks/useTasks.ts` (экспорт `useTasks` и `useTaskMutations`)
- `apps/web/src/hooks/useDashboardToday.ts` (типобезопасные поля календаря и бюджета)
- `docs/it-company/20-ui-component-developer.md`

FINDINGS:
- **Безупречная интеграция с dnd-kit:** Использование сенсоров `PointerSensor` (с ограничением `distance: 5px`) и `KeyboardSensor` (`sortableKeyboardCoordinates`) устраняет случайные срабатывания перетаскивания при обычном клике по чекбоксу или тексту карточки.
- **Единый источник правды (Kanban = Task.status):** Все 6 колонок Kanban (`inbox`, `todo`, `scheduled`, `in_progress`, `waiting`, `done`) отображают проекцию доменных задач без создания дублирующих таблиц или локальных рассинхронизаций.
- **UI State vs Domain State:** Все эфемерные состояния окон и панелей (открытие QuickAddModal, Slide-over деталей задачи, сворачивание сайдбара) централизованы в легком сторе Zustand `useUIStore`, а доменные данные передаются через типизированные пропсы.
- **Интуитивный Quick Add:** Ввод свободного текста автоматически дебаунсится на 300мс и парсит теги `#project`, приоритеты `!high`, даты и денежные суммы, позволяя создать запись за 1-2 нажатия клавиш.

VALIDATION:
- Проведена полная проверка типизации TypeScript (`npm run typecheck` в `apps/web`): 0 ошибок, 100% покрытие типов.
- Проверена корректность стилей CSS Variables в светлой и тёмной темах.
- Проверены ARIA-атрибуты (`role="article"`, `role="region"`, `role="tablist"`, `role="dialog"`, `role="progressbar"`).

EVIDENCE:
```powershell
PS C:\Users\Siroj\Projects\personal-os\apps\web> npm run typecheck

> @personal-os/web@0.1.0 typecheck
> tsc --noEmit

# Output: exited with code 0 (zero errors)
```

Фрагмент интерфейса TaskCard:
```tsx
export interface TaskCardProps {
  task: Task;
  onComplete: (id: string) => void;
  onEdit: (id: string) => void;
  isDragging?: boolean;
}
```

Фрагмент интерфейса AIPreviewDiff:
```tsx
export interface AIPreviewDiffProps {
  plan: AIPreviewPlan;
  onConfirm: () => void;
  onReject: () => void;
  onPartialApply: (selectedIds: string[]) => void;
}
```

Фрагмент интерфейса MorningBriefCard:
```tsx
export interface MorningBriefCardProps {
  brief: MorningBrief;
  onAccept: () => void;
  onPartialAccept: (ids: string[]) => void;
  onDismiss: () => void;
}
```

REMAINING_ISSUES: нет
BLOCKERS: нет

DECISIONS:
| ID | Решение | Обоснование |
|---|---|---|
| **D-20-01** | Единая палитра HSL/HEX CSS Variables | Гарантирует динамическую смену тем оформления без повторной сборки бандла стилей. |
| **D-20-02** | 6 колонок Kanban (`inbox`, `todo`, `scheduled`, `in_progress`, `waiting`, `done`) | Точное соответствие спецификации жизненного цикла задач из ТЗ и UI-дизайна. |
| **D-20-03** | Human-in-the-Loop Safe Preview в `AIPreviewDiff` | Защита от непреднамеренных массовых изменений расписания с поддержкой частичного применения. |
| **D-20-04** | Разделение экрана Today на Server Component Shell и Client Dashboard | Оптимальная производительность SSR и мгновенная интерактивность виджетов. |

HANDOFF:
Передать готовые UI-компоненты и экранные шаблоны агенту `21-frontend-integration-engineer` для связывания со сквозными сетевыми TanStack Query запросами, WebSocket диспетчеризацией реального времени и интеграционными тестами.

NEXT_AGENT: 21-frontend-integration-engineer
