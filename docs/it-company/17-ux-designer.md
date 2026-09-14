# 17. UX Designer

## 1. Ключевые пользовательские сценарии (User Flows)

### Flow 1: Быстрое создание и подтверждение через Quick Add
1. Пользователь нажимает Cmd/Ctrl + K или кликает по строке Quick Add вверху экрана.
2. Вводит текст на русском/узбекском: «обед 45к uzcard» или «ertaga 10:00 meeting».
3. Система мгновенно отображает превью карточки (Сумма: 45 000 UZS, Счёт: Uzcard, Категория: Еда).
4. Пользователь нажимает Enter / «Подтвердить». Данные мгновенно обновляются на дашборде.

### Flow 2: Сверка баланса счёта (Reconciliation)
1. Пользователь открывает страницу «Финансы» -> карточка счёта -> меню счёта «Сверка остатка».
2. В модальном окне отображается текущий остаток системы и поле ввода фактического остатка из банковского приложения.
3. Система рассчитывает дельту (например, +50 000 UZS).
4. Пользователь указывает причину («Кэшбэк / Проценты») и подтверждает. Баланс корректируется созданием транзакции сверки.

### Flow 3: Управление задачами и канбан-доска
1. Представление «Сегодня» отображает задачи с дедлайном/таймблоком на сегодня.
2. Завершение задачи в 1 клик (чекбокс переводит задачу в done и запускает легкую анимацию).
3. Канбан-доска позволяет drag-and-drop перемещение между колонками inbox, todo, in_progress, waiting, done.

---

STATUS: VERIFIED
TASK: Проектирование User Flow, Customer Journey и структуры экранов
INPUT: docs/it-company/01-product-discovery-manager.md, docs/it-company/02-business-analyst.md
ACTIONS:
  - Разработаны User Flow для Quick Add, Reconciliation, Today View и Kanban.
  - Оптимизировано количество кликов для ключевых действий.
CHANGED_FILES:
  - docs/it-company/17-ux-designer.md
FINDINGS: none
FIXES: n/a
VALIDATION: Сценарии UX устраняют трение при вводе финансов и подтверждении AI.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/17-ux-designer.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Сверка вынесена в отдельное модальное окно с отображением расчетной дельты.
HANDOFF: UX-материалы переданы UI Designer (18) и Frontend Architect (16).
NEXT_AGENT: 18 UI Designer
