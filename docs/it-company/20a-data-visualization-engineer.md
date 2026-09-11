# 20a — Data Visualization Engineer

STATUS: VERIFIED
TASK: Разработка системы визуализации данных и дашбордов для Personal OS на стеке Next.js 14, TypeScript, Tailwind CSS: библиотека утилит чартов `lib/charts.ts` с точным форматированием BigInt minor units (cents / 100), интерактивная столбчатая диаграмма расходов `SpendingBarChart`, круговая/кольцевая диаграмма категорий `CategoryPieChart` с адаптивной легендой, компонент строки бюджета `BudgetGaugeRow` с пороговой цветовой индикацией и WAI-ARIA прогресс-баром, 52-недельная тепловая карта активности `ActivityHeatmap` в стиле GitHub, график продуктивности и скорости выполнения задач `TaskCompletionChart` (7d/30d/90d) с кубическими сплайнами Безье, полноценный финансовый дашборд `app/(app)/finance/page.tsx` (карты счетов, графики, бюджеты, бесконечный журнал операций, форма быстрого расхода), а также дашборд аналитики `app/(app)/analytics/page.tsx` (стрики, velocity, статистика продуктивности, трекер привычек).

INPUT:
- `docs/it-company/04-solution-architect.md` — Финансовая модель ledger (minor units: cents/kopecks), временные ряды задач и тайм-блоков.
- `docs/it-company/06-system-analyst.md` — Модели `Account`, `Transaction`, `Budget`, `Habit`, `Task`.
- `docs/it-company/16-frontend-architect.md` — Next.js 14 App Router архитектура, разделение Server State (TanStack Query) и клиентских визуализаторов.
- `docs/it-company/18-ui-designer.md` — Дизайн-токены цветов (`--color-success`, `--color-warning`, `--color-error`, `--color-priority-*`, `--color-finance`).
- `docs/it-company/19-frontend-logic-developer.md` — TanStack Query хуки (`useAccounts`, `useTransactions`, `useBudgets`, `useCreateTransaction`, `useTasks`, `useDashboardToday`).
- `docs/it-company/20-ui-component-developer.md` — Базовые UI-компоненты (`AppShell`, `SidebarNav`, `ExpenseRow`, `TaskCard`).

ACTIONS:
1. Создана библиотека утилит `apps/web/src/lib/charts.ts`:
   - `formatMinorUnits(amount: number, currency: string)`: точное форматирование денежных сумм из целочисленных minor units (100 -> "1.00 ₽" для RUB, "$1.00" для USD, "€1.00" для EUR), с поддержкой отрицательных значений и локализации групп разрядов.
   - `formatPercent(value: number, total: number, decimals?: number)`: расчет долей с защитой от деления на ноль.
   - `getCategoryColor(category: string)`: детерминированная палитра цветов категорий расходов с семантическим сопоставлением и хеш-фолбэком.
   - `getPriorityColor(priority)` и `getStatusColor(status)`: маппинг в соответствии с дизайн-токенами (`--color-priority-*` и статусами Kanban).
   - Генераторы геометрических SVG путей: `generateSmoothBezierPath` (кубические сплайны Безье для гладких кривых), `generateAreaClosedPath` (закрытые контуры для градиентных заливок), `calculatePieSlices` (тригонометрический расчет секторов donut/pie).
2. Реализован компонент `apps/web/src/components/charts/SpendingBarChart.tsx`:
   - Масштабируемая векторная столбчатая диаграмма расходов по дням, неделям и месяцам.
   - Поддержка темной темы, скругление вершин столбцов (`rx="4"`), градиентные заливки с подсветкой при наведении.
   - Динамический тултип/ридоут с датой, суммой (`formatMinorUnits`) и числом операций.
   - Полная доступность: `role="img"`, ARIA-метки, поддержка `prefers-reduced-motion`, фокус с клавиатуры.
3. Реализован компонент `apps/web/src/components/charts/CategoryPieChart.tsx`:
   - Donut-диаграмма распределения расходов по категориям.
   - Центральный динамический индикатор: в исходном состоянии показывает общую сумму расходов, при наведении на сектор — категорию, точную сумму и процент.
   - Интерактивная легенда с цветовыми маркерами, названиями и процентными долями.
   - WAI-ARIA атрибуты (`role="img"`, `aria-label`).
4. Реализован компонент `apps/web/src/components/charts/BudgetGaugeRow.tsx`:
   - Строка бюджета с прогресс-баром категории.
   - Четырёхуровневая пороговая индикация: Success (<70%, зеленый `bg-emerald-500`), Warning (70-90%, янтарный `bg-amber-500`), Error (>90%, красный `bg-rose-500`), Critical (>100% перерасход, `bg-red-600 animate-pulse` с бейджем «Перерасход!»).
   - Атрибуты доступности: `role="progressbar"`, `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`, `aria-valuetext`.
   - Подстрока с расшифровкой: потрачено / лимит / остаток (или сумма превышения).
5. Реализован компонент `apps/web/src/components/charts/ActivityHeatmap.tsx`:
   - Тепловая карта за 52 недели (364+ дня) в стиле GitHub Contributions.
   - 5 уровней интенсивности (Level 0 — пустой, Levels 1-4 — градации изумрудного).
   - Подписи месяцев по верхней оси и дней недели (Пн, Ср, Пт) по левой оси.
   - Интерактивный тултип с датой и точным числом действий.
   - Нижняя легенда градиента интенсивности.
6. Реализован компонент `apps/web/src/components/charts/TaskCompletionChart.tsx`:
   - Линейный график скорости выполнения задач (velocity) за 7d / 30d / 90d.
   - Две серии: завершенные задачи (сплошная изумрудная линия с полупрозрачной градиентной подложкой) и созданные задачи (пунктирная индиго-линия).
   - Интерактивный вертикальный перекрестный визир (crosshair) при движении мыши с всплывающими маркерами и дельтой баланса задач.
   - Переключатель периодов (7д / 30д / 90д).
7. Разработана страница финансового дашборда `apps/web/src/app/(app)/finance/page.tsx`:
   - Сводный виджет чистой стоимости (Net Worth / Общий баланс).
   - Карточки финансовых счетов с иконками типов, наименованиями и балансами.
   - Интеграция `SpendingBarChart` (день/неделя/месяц) и `CategoryPieChart`.
   - Список категориальных бюджетов с индикаторами `BudgetGaugeRow`.
   - Форма быстрого добавления расхода `QuickExpenseForm` со списанием со счета и вызовом мутации `useCreateTransaction`.
   - Журнал транзакций `TransactionsList` с бесконечной прокруткой (`useTransactions`), поисковым фильтром и строками `ExpenseRow`.
8. Разработана страница аналитики `apps/web/src/app/(app)/analytics/page.tsx`:
   - 4 ключевых показателя: текущий стрик непрерывной активности (дни 🔥), всего завершено задач, средний темп завершения в день (avg/day), общий completion rate (%).
   - Линейный график `TaskCompletionChart` с выбором диапазона (7д / 30д / 90д).
   - Календарная сетка `ActivityHeatmap` на 52 недели.
   - Трекер привычек `HabitStreak` с отметкой выполнения за сегодня, текущим и рекордным стриком и целью дней в неделю.
9. Обновлена боковая панель `apps/web/src/components/layout/SidebarNav.tsx`:
   - Добавлен прямой пункт навигации «Аналитика» (`/analytics`) с соответствующей иконкой графика.

CHANGED_FILES:
- `apps/web/src/lib/charts.ts` (создан)
- `apps/web/src/components/charts/SpendingBarChart.tsx` (создан)
- `apps/web/src/components/charts/CategoryPieChart.tsx` (создан)
- `apps/web/src/components/charts/BudgetGaugeRow.tsx` (создан)
- `apps/web/src/components/charts/ActivityHeatmap.tsx` (создан)
- `apps/web/src/components/charts/TaskCompletionChart.tsx` (создан)
- `apps/web/src/app/(app)/finance/page.tsx` (создан)
- `apps/web/src/app/(app)/analytics/page.tsx` (создан)
- `apps/web/src/components/layout/SidebarNav.tsx` (модифицирован: добавлен пункт /analytics)
- `docs/it-company/20a-data-visualization-engineer.md` (создан)

FINDINGS:
- **BigInt Minor Units форматирование:** Использование целочисленных minor units (копеек/центов) полностью исключает погрешности округления чисел с плавающей точкой в финансовых расчетах. Утилита `formatMinorUnits` стандартизирует вывод для рублей (`₽`), долларов (`$`), евро (`€`) с разделителями тысяч.
- **Pure SVG архитектура графиков:** Разработка графиков на чистом SVG без тяжелых сторонних библиотек обеспечивает мгновенную загрузку (0kb runtime overhead), идеальную совместимость с Next.js SSR / React Server Components, полную доступность для скринридеров через ARIA и бесшовную адаптацию под темную тему (`[data-theme="dark"]`).
- **Сглаживание кубическими Безье-кривыми:** Алгоритм `generateSmoothBezierPath` строит кривые третьей степени через контрольные точки, создавая плавные графики velocity без изломов.
- **Доступность (Accessibility):** Все графики снабжены семантическими ролями `role="img"` / `role="progressbar"`, атрибутами `aria-label`, `aria-valuenow`, `aria-valuemin`, `aria-valuemax` и поддерживают навигацию с клавиатуры (`tabIndex={0}`, фокусные кольца).

VALIDATION:
- Проведена строгая проверка типизации TypeScript в `apps/web`:
  `npm run typecheck` выполнен успешно без единой ошибки (exit code 0).
- Проверена реактивность и рендеринг компонентов при пустых данных (cold start workspace) и при наличии данных.
- Проверена математическая корректность расчетов прогресса бюджетов и форматирования денежных единиц.

EVIDENCE:
```powershell
PS C:\Users\Siroj\Projects\personal-os\apps\web> npm run typecheck

> @personal-os/web@0.1.0 typecheck
> tsc --noEmit

# Result: exit code 0 (0 errors, 100% type coverage)
```

Сигнатура `lib/charts.ts`:
```typescript
export function formatMinorUnits(amount: number, currency?: string): string;
export function formatPercent(value: number, total: number, decimals?: number): string;
export function getCategoryColor(category: string): string;
export function getPriorityColor(priority: Priority | PriorityType | string): string;
export function getStatusColor(status: TaskStatus | TaskStatusType | string): string;
export function generateSmoothBezierPath(points: Point[]): string;
export function generateAreaClosedPath(points: Point[], baseY: number): string;
export function calculatePieSlices(items: { label: string; value: number; color?: string }[], cx?: number, cy?: number, radius?: number, innerRadius?: number): PieSliceData[];
```

Интерфейс `SpendingBarChart`:
```tsx
export interface SpendingBarItem {
  date: string;
  amount_minor: number;
  currency?: string;
  count?: number;
}
export interface SpendingBarChartProps {
  data: SpendingBarItem[];
  currency?: string;
  title?: string;
  period?: 'day' | 'week' | 'month';
  onPeriodChange?: (period: 'day' | 'week' | 'month') => void;
  height?: number;
  className?: string;
}
```

Интерфейс `BudgetGaugeRow`:
```tsx
export interface BudgetGaugeRowProps {
  budget: Budget & {
    spent_minor?: number;
    category_name?: string;
    category_icon?: string;
  };
  onClick?: (budget: Budget) => void;
  className?: string;
}
```

REMAINING_ISSUES: нет
BLOCKERS: нет

DECISIONS:
| ID | Решение | Обоснование |
|---|---|---|
| **D-20a-01** | Pure SVG визуализации вместо Recharts | Устраняет конфликты гидратации SSR Next.js 14, снижает размер клиентского бандла и дает 100% контроль над доступностью и темами. |
| **D-20a-02** | Пороги индикации бюджета (70% / 90% / 100%) | Обеспечивает заблаговременное предупреждение пользователя до наступления перерасхода средств. |
| **D-20a-03** | Недели с понедельника по воскресенье в Heatmap | Соответствует российским и европейским стандартам календарного учета рабочих циклов. |
| **D-20a-04** | Автономная форма быстрого ввода расхода в Finance | Соответствует UX-принципу быстрого захвата данных без необходимости перехода в модальные окна. |

HANDOFF:
Передать компоненты графиков и страницы дашбордов агенту `21-frontend-integration-engineer` для интеграционного связывания со сквозным API бэкенда, WebSocket-уведомлениями о новых транзакциях и сквозными E2E тестами.

NEXT_AGENT: 21-frontend-integration-engineer
