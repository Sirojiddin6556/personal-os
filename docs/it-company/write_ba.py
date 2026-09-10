#!/usr/bin/env python3
# -*- coding: utf-8 -*-
content = """\
# 02 — Business Analyst

STATUS: VERIFIED
TASK: Создать полный пакет бизнес-аналитики для Personal OS — User Stories, Use Cases, Business Rules, AC-матрица
INPUT: docs/it-company/01-product-discovery-manager.md (Product Vision, MVP Scope, Tech Stack, User Segments)
ACTIONS:
- Написаны User Stories (65 шт.) по 13 доменам MVP
- Описаны 7 детальных Use Cases для критических потоков
- Зафиксированы Business Rules по доменам
- Составлена AC-матрица (UC → AC → Priority → MVP)

---

## 1. USER STORIES

### 1.1 Домен: Quick Add / Inbox

> Быстрый захват любой сущности за ≤3 действия из любого контекста

**US-QA-01**
Как Knowledge Worker, я хочу ввести текст в одно поле и получить распознанную задачу с датой и приоритетом, чтобы не тратить время на заполнение форм.

Acceptance Criteria:
- AC-1: Поле Quick Add доступно с любой страницы (горячая клавиша Cmd/Ctrl+K)
- AC-2: Парсер распознаёт дату в форматах "завтра", "пт", "12 июл", "2026-07-12"
- AC-3: Парсер распознаёт приоритет "!1", "!2", "!3" → P1/P2/P3
- AC-4: Парсер распознаёт проект через #ProjectName
- AC-5: Preview карточка показывается до сохранения (< 200ms)

**US-QA-02**
Как Indie Hacker, я хочу захватить расход через Telegram, чтобы фиксировать траты прямо в момент оплаты.

Acceptance Criteria:
- AC-1: Бот принимает текстовые сообщения
- AC-2: Из "кофе 250р" → Transaction(amount=250, currency=RUB, category=auto)
- AC-3: Из "потратил 3500 на такси" → Transaction(amount=3500, category=transport)
- AC-4: Ответ бота подтверждает сохранение с деталями (≤ 2 сек)

**US-QA-03**
Как пользователь, я хочу выбрать тип захватываемой сущности (задача/событие/расход/заметка), чтобы данные попадали в правильный домен.

Acceptance Criteria:
- AC-1: По умолчанию тип = Task
- AC-2: Смена типа через префикс: "/event", "/expense", "/note" или через UI-переключатель
- AC-3: Парсер автоматически определяет тип по ключевым словам ("встреча" → event, "купил" → expense)
- AC-4: Выбранный тип запоминается в session storage до закрытия

**US-QA-04**
Как Knowledge Worker, я хочу видеть мой Inbox (непроработанные элементы), чтобы регулярно их разбирать.

Acceptance Criteria:
- AC-1: Inbox отображает все items без project/date assignment
- AC-2: Inbox badge показывает количество необработанных (0–99, 99+)
- AC-3: Из Inbox можно назначить проект, дату, приоритет за 1 клик
- AC-4: После assignment элемент уходит из Inbox

**US-QA-05**
Как пользователь, я хочу отменить последнее действие Quick Add, чтобы исправить случайно добавленный элемент.

Acceptance Criteria:
- AC-1: Кнопка "Undo" в toast-уведомлении активна 5 секунд
- AC-2: Undo удаляет сущность (soft-delete, audit trail сохраняется)
- AC-3: После закрытия toast undo недоступен

---

### 1.2 Домен: Today Dashboard

> Агрегированный вид текущего дня — задачи + события + финансы + прогресс

**US-TODAY-01**
Как Knowledge Worker, я хочу видеть сводку дня при открытии приложения, чтобы сразу понять что важно сегодня.

Acceptance Criteria:
- AC-1: Dashboard загружается ≤ 2 сек
- AC-2: Показывает: задачи на сегодня (due today), события из календаря, бюджет дня
- AC-3: Данные агрегируются из Tasks, Calendar, Finance — нет отдельного хранилища Today
- AC-4: Обновляется при изменении любого домена (WebSocket/polling 30 сек)

**US-TODAY-02**
Как пользователь, я хочу видеть прогресс выполнения задач за день, чтобы оценить продуктивность.

Acceptance Criteria:
- AC-1: Progress bar показывает done/total задач на сегодня
- AC-2: Завершённые задачи отмечаются с timestamp
- AC-3: Completion rate за последние 7 дней — mini-chart

**US-TODAY-03**
Как Knowledge Worker, я хочу видеть следующее событие в календаре с обратным отсчётом, чтобы не опаздывать на встречи.

Acceptance Criteria:
- AC-1: "Следующее событие" виджет показывает название, время, участников
- AC-2: Обратный отсчёт обновляется каждую минуту
- AC-3: За 10 минут до события — браузерный Push notification

**US-TODAY-04**
Как Indie Hacker, я хочу видеть дневной бюджет и сколько уже потрачено, чтобы контролировать расходы.

Acceptance Criteria:
- AC-1: Виджет показывает spent/budget для текущего дня
- AC-2: При превышении бюджета — красная индикация
- AC-3: Сумма считается из posted transactions за текущий calendar day

**US-TODAY-05**
Как пользователь, я хочу из Dashboard напрямую добавить задачу, чтобы не переходить на другую страницу.

Acceptance Criteria:
- AC-1: Quick Add доступен прямо с Dashboard
- AC-2: Добавленная задача немедленно появляется в Today-списке (optimistic update)
- AC-3: При ошибке сохранения — rollback и toast с ошибкой

---

### 1.3 Домен: Tasks

**US-TASK-01**
Как Knowledge Worker, я хочу создать задачу с названием, дедлайном, приоритетом и проектом, чтобы структурировать работу.

Acceptance Criteria:
- AC-1: Форма: title (required), due_date, priority (P1/P2/P3/none), project_id
- AC-2: Задача создаётся со статусом BACKLOG по умолчанию
- AC-3: Валидация: title ≥ 1 символ, ≤ 500 символов
- AC-4: workspace_id устанавливается автоматически из контекста сессии

**US-TASK-02**
Как пользователь, я хочу переводить задачу между статусами (Backlog→Todo→In Progress→Done), чтобы отражать реальный прогресс.

Acceptance Criteria:
- AC-1: Допустимые статусы: BACKLOG, TODO, IN_PROGRESS, DONE, CANCELLED, ARCHIVED
- AC-2: Переходы строго по state machine
- AC-3: Статус DONE записывает completed_at timestamp
- AC-4: CANCELLED требует подтверждения если есть незавершённые subtasks

**US-TASK-03**
Как Knowledge Worker, я хочу добавлять подзадачи к задаче, чтобы декомпозировать сложную работу.

Acceptance Criteria:
- AC-1: Subtask — это Task с parent_task_id
- AC-2: Вложенность максимум 2 уровня (task → subtask; sub-subtask запрещён)
- AC-3: Родительская задача показывает прогресс subtasks (N/M completed)
- AC-4: При DONE родительской задачи — предупреждение о незавершённых subtasks

**US-TASK-04**
Как Knowledge Worker, я хочу устанавливать повторяющиеся задачи (daily/weekly/monthly), чтобы не создавать их вручную.

Acceptance Criteria:
- AC-1: Повтор: DAILY, WEEKLY (day of week), MONTHLY (day of month)
- AC-2: При DONE повторяющейся задачи — создаётся новый экземпляр с следующей датой
- AC-3: Изменение recurring rule применяется только к будущим экземплярам
- AC-4: Возможность завершить серию (end_date или after N times)

**US-TASK-05**
Как пользователь, я хочу видеть просроченные задачи отдельно, чтобы приоритизировать их.

Acceptance Criteria:
- AC-1: Overdue — вычисляемое состояние: due_date < today AND status NOT IN (DONE, CANCELLED, ARCHIVED)
- AC-2: Overdue НЕ является отдельным статусом в БД
- AC-3: Раздел "Просроченные" показывается вверху списка задач
- AC-4: Overdue badge показывает количество в навигации

**US-TASK-06**
Как Knowledge Worker, я хочу фильтровать и сортировать задачи по приоритету, проекту, дате, чтобы находить нужные быстро.

Acceptance Criteria:
- AC-1: Фильтры: status, priority, project_id, due_date (range)
- AC-2: Сортировка: due_date, priority, created_at, title (asc/desc)
- AC-3: Активные фильтры сохраняются в URL query params
- AC-4: "Сбросить фильтры" одним кликом

---

### 1.4 Домен: Kanban

**US-KAN-01**
Как Студент, я хочу видеть задачи в виде Kanban-доски по статусам, чтобы наглядно отслеживать прогресс.

Acceptance Criteria:
- AC-1: Колонки: BACKLOG, TODO, IN_PROGRESS, DONE (порядок фиксирован)
- AC-2: Карточки — это Tasks; нет отдельной таблицы Kanban cards в БД
- AC-3: Drag & drop карточки между колонками меняет Task.status
- AC-4: Kanban и List view — переключаемые представления одного набора данных

**US-KAN-02**
Как пользователь, я хочу перетащить карточку в другую колонку, чтобы изменить статус задачи без открытия формы.

Acceptance Criteria:
- AC-1: Drag & drop работает на desktop (мышь) и mobile (touch)
- AC-2: Анимация перетаскивания плавная (60fps)
- AC-3: Невалидный переход — карточка возвращается на место + toast
- AC-4: Оптимистичное обновление UI, rollback при ошибке API

**US-KAN-03**
Как Knowledge Worker, я хочу фильтровать Kanban по проекту, чтобы видеть только задачи конкретного проекта.

Acceptance Criteria:
- AC-1: Фильтр "Проект" сохраняется в URL
- AC-2: При выборе проекта колонки показывают только его задачи
- AC-3: "Все проекты" — вид по умолчанию

**US-KAN-04**
Как пользователь, я хочу создать задачу прямо из Kanban-колонки, чтобы не переходить в отдельную форму.

Acceptance Criteria:
- AC-1: Кнопка "+ Add card" в каждой колонке
- AC-2: Inline-форма: только title; остальное редактируется потом
- AC-3: Новая карточка создаётся со статусом данной колонки

**US-KAN-05**
Как пользователь, я хочу видеть количество задач в каждой колонке, чтобы оценить WIP.

Acceptance Criteria:
- AC-1: Badge с количеством в заголовке каждой колонки
- AC-2: WIP limit (опционально) — предупреждение при превышении лимита IN_PROGRESS

---

### 1.5 Домен: Projects

**US-PROJ-01**
Как Knowledge Worker, я хочу создать проект с названием, описанием и дедлайном, чтобы группировать связанные задачи.

Acceptance Criteria:
- AC-1: Поля: name (required), description, deadline, color, status (ACTIVE/ON_HOLD/COMPLETED/ARCHIVED)
- AC-2: Проект принадлежит workspace (workspace_id)
- AC-3: Slug генерируется автоматически из name (url-safe)

**US-PROJ-02**
Как пользователь, я хочу видеть прогресс проекта в % завершённых задач, чтобы понимать насколько близок финиш.

Acceptance Criteria:
- AC-1: Progress = count(tasks WHERE status=DONE) / count(tasks) * 100
- AC-2: Прогресс вычисляется on-the-fly, не хранится отдельно
- AC-3: При 0 задач — прогресс не отображается (защита от деления на 0)

**US-PROJ-03**
Как Indie Hacker, я хочу архивировать завершённый проект, чтобы он не засорял рабочее пространство.

Acceptance Criteria:
- AC-1: Архивирование требует подтверждения если есть незавершённые задачи
- AC-2: Архивированный проект скрыт из основного списка
- AC-3: Задачи архивированного проекта получают статус ARCHIVED
- AC-4: Данные сохраняются (soft archive)

**US-PROJ-04**
Как Knowledge Worker, я хочу видеть все задачи проекта на отдельной странице, чтобы управлять ими в контексте проекта.

Acceptance Criteria:
- AC-1: Страница проекта имеет вкладки: List, Kanban, Calendar
- AC-2: Переключение вида не перезагружает данные (TanStack Query cache)

---

### 1.6 Домен: Calendar + Time Blocks

**US-CAL-01**
Как Knowledge Worker, я хочу видеть задачи с дедлайнами на календаре, чтобы планировать время.

Acceptance Criteria:
- AC-1: Tasks с due_date отображаются на соответствующем дне
- AC-2: Calendar events отображаются отдельным цветом
- AC-3: Time blocks отображаются как события
- AC-4: Вид: месяц / неделя / день — переключаемые

**US-CAL-02**
Как пользователь, я хочу создать time block для работы над задачей, чтобы зарезервировать время.

Acceptance Criteria:
- AC-1: Time block: title, start_datetime, end_datetime, linked_task_id (optional)
- AC-2: Создание через drag на календаре или через форму
- AC-3: Time block не пересекается с другим time block (предупреждение)

**US-CAL-03**
Как Knowledge Worker, я хочу видеть загрузку дня/недели, чтобы видеть свободные слоты.

Acceptance Criteria:
- AC-1: Тепловая карта занятости (free / busy / overloaded) по часам
- AC-2: Учитываются: calendar events + time blocks
- AC-3: AI Planning использует эти данные при генерации предложений

**US-CAL-04**
Как пользователь, я хочу перетащить событие на другое время, чтобы перенести встречу.

Acceptance Criteria:
- AC-1: Drag & drop события изменяет start/end datetime
- AC-2: Если событие синхронизировано с Google — изменение propagates в Google Calendar
- AC-3: Оптимистичный UI + rollback при ошибке

---

### 1.7 Домен: Google Calendar Sync

**US-GCAL-01**
Как Knowledge Worker, я хочу подключить Google Calendar, чтобы все мои встречи отображались в Personal OS.

Acceptance Criteria:
- AC-1: OAuth 2.0 flow (offline access, refresh token хранится encrypted)
- AC-2: После авторизации — немедленная полная синхронизация
- AC-3: Все calendars перечислены; можно выбрать какие синхронизировать

**US-GCAL-02**
Как пользователь, я хочу чтобы изменения в Google Calendar автоматически отражались в Personal OS.

Acceptance Criteria:
- AC-1: Webhook от Google обрабатывается ≤ 5 сек
- AC-2: Fallback incremental sync каждые 15 мин (Celery beat)
- AC-3: Удалённые в Google события помечаются deleted=True (soft delete)

**US-GCAL-03**
Как пользователь, я хочу создавать события в Personal OS и видеть их в Google Calendar.

Acceptance Criteria:
- AC-1: Event из Personal OS → создаётся в Google Calendar (two-way)
- AC-2: google_event_id сохраняется для идентификации при sync
- AC-3: Конфликт — Personal OS wins, пользователь уведомлён

**US-GCAL-04**
Как пользователь, я хочу отключить синхронизацию, чтобы Google Calendar работал независимо.

Acceptance Criteria:
- AC-1: Отключение отзывает Google OAuth token
- AC-2: Локальные события остаются (не удаляются)
- AC-3: google_event_id очищается; события — "local only"

---

### 1.8 Домен: Finance

**US-FIN-01**
Как Indie Hacker, я хочу добавить расход с суммой, категорией и датой, чтобы вести учёт трат.

Acceptance Criteria:
- AC-1: Поля: amount (required, > 0), currency, category_id, account_id, date, note
- AC-2: Сумма хранится как integer minor units (копейки/центы)
- AC-3: После сохранения транзакция immutable (posted=True)
- AC-4: Correction через новую противоположную транзакцию

**US-FIN-02**
Как пользователь, я хочу создать бюджет по категории на месяц, чтобы контролировать расходы.

Acceptance Criteria:
- AC-1: Budget: category_id, period (MONTHLY/WEEKLY), amount_limit, workspace_id
- AC-2: Остаток = limit - sum(transactions for period & category)
- AC-3: Уведомление при достижении 80% и 100% лимита
- AC-4: Перерасход не блокирует добавление транзакций (предупреждение)

**US-FIN-03**
Как Indie Hacker, я хочу видеть отчёт расходов по категориям за месяц, чтобы анализировать куда уходят деньги.

Acceptance Criteria:
- AC-1: Pie chart / bar chart расходов по категориям
- AC-2: Период: текущий месяц (по умолчанию), выбор диапазона дат
- AC-3: Экспорт в CSV

**US-FIN-04**
Как пользователь, я хочу создать несколько счетов (карта, наличные, накопительный).

Acceptance Criteria:
- AC-1: Account: name, type (CHECKING/SAVINGS/CASH/CREDIT), currency, initial_balance
- AC-2: Balance = initial_balance + sum(income) - sum(expense)
- AC-3: Transfer между счетами создаёт 2 транзакции (debit + credit)

**US-FIN-05**
Как пользователь, я хочу добавить расход через Telegram одной строкой.

Acceptance Criteria:
- AC-1: "500 обед" → expense 500, category=Food (auto-detect)
- AC-2: "доход 50000 зарплата" → income transaction
- AC-3: Ответ бота: детали транзакции + "Исправить?" кнопки

---

### 1.9 Домен: Telegram Bot

**US-TG-01**
Как пользователь, я хочу связать Telegram-аккаунт с Personal OS.

Acceptance Criteria:
- AC-1: /start → deeplink с одноразовым token
- AC-2: Token привязывает telegram_user_id к user_id (TTL 10 мин)
- AC-3: Повторная привязка перезаписывает старую связь

**US-TG-02**
Как Indie Hacker, я хочу добавить задачу через Telegram.

Acceptance Criteria:
- AC-1: Любой текст без команды → создаётся Task (если не распознан другой тип)
- AC-2: "/task Купить молоко завтра !2" → Task с due=tomorrow, priority=P2
- AC-3: Ответ: "Задача создана: [название]" + кнопки Edit/Cancel

**US-TG-03**
Как пользователь, я хочу получать утренний брифинг в Telegram.

Acceptance Criteria:
- AC-1: Morning Brief отправляется в 08:00 по часовому поясу пользователя
- AC-2: Содержит: задачи на сегодня, события, финансовый остаток дня
- AC-3: AI-комментарий (1-2 предложения) о загрузке дня
- AC-4: Настраиваемое время в User Preferences

**US-TG-04**
Как пользователь, я хочу получать напоминания о задачах через Telegram.

Acceptance Criteria:
- AC-1: Напоминание за N минут до due_date (настраивается)
- AC-2: "Задача просрочена" уведомление если статус не DONE к due_date
- AC-3: Одна задача = максимум 2 напоминания (pre + overdue)

**US-TG-05**
Как пользователь, я хочу получать уведомления о превышении бюджета в Telegram.

Acceptance Criteria:
- AC-1: При 80% использования бюджета → предупреждение
- AC-2: При 100% → "Бюджет исчерпан" сообщение
- AC-3: Не более 1 уведомления в день на категорию

---

### 1.10 Домен: Notifications

**US-NOTIF-01**
Как пользователь, я хочу получать Push-уведомления в браузере о важных событиях.

Acceptance Criteria:
- AC-1: Web Push через Service Worker (PWA)
- AC-2: Типы: task_reminder, event_start, budget_alert, morning_brief
- AC-3: Пользователь может управлять типами уведомлений в настройках

**US-NOTIF-02**
Как пользователь, я хочу видеть историю уведомлений в приложении.

Acceptance Criteria:
- AC-1: Notification Center показывает последние 50 уведомлений
- AC-2: Непрочитанные отмечены синим, прочитанные — серым
- AC-3: "Отметить все как прочитанные" одной кнопкой

**US-NOTIF-03**
Как пользователь, я хочу настроить quiet hours, чтобы не получать уведомления ночью.

Acceptance Criteria:
- AC-1: Диапазон quiet hours в User Preferences
- AC-2: Уведомления в quiet hours откладываются до конца периода
- AC-3: Critical уведомления (security) не блокируются

---

### 1.11 Домен: Morning Brief

**US-MB-01**
Как Knowledge Worker, я хочу получать ежедневный дайджест задач и событий.

Acceptance Criteria:
- AC-1: Brief генерируется в 07:45 (за 15 мин до отправки) Celery task
- AC-2: Содержит: overdue tasks, today tasks, today events, budget status
- AC-3: AI добавляет 1-3 предложения с рекомендацией (can be disabled)

**US-MB-02**
Как пользователь, я хочу просмотреть утренний брифинг в веб-приложении.

Acceptance Criteria:
- AC-1: Morning Brief доступен как страница /morning-brief
- AC-2: Показывается последний Brief + история за 7 дней
- AC-3: Brief не перегенерируется при повторном просмотре (cached)

---

### 1.12 Домен: AI Capture + AI Schedule Preview

**US-AI-01**
Как Knowledge Worker, я хочу попросить AI расставить задачи по расписанию.

Acceptance Criteria:
- AC-1: AI получает: список задач (priority, estimate), свободные слоты из Calendar
- AC-2: AI предлагает расписание в виде Time Blocks (preview, не применено)
- AC-3: Пользователь видит preview и нажимает "Применить" или "Отклонить"
- AC-4: Apply создаёт Time Blocks через Policy Engine (не прямой SQL)

**US-AI-02**
Как пользователь, я хочу чтобы AI разобрал мой нечёткий текст и создал структурированные задачи.

Acceptance Criteria:
- AC-1: "Нужно подготовить презентацию к пятнице и купить продукты" → 2 задачи
- AC-2: AI определяет: title, due_date, priority из контекста
- AC-3: Preview показывает распознанные задачи до сохранения
- AC-4: Пользователь может редактировать каждое поле перед confirm

**US-AI-03**
Как пользователь, я хочу чтобы AI не мог напрямую изменять мои данные.

Acceptance Criteria:
- AC-1: AI предлагает actions, пользователь подтверждает (Confirm/Reject)
- AC-2: После Confirm — actions выполняются через Policy Engine
- AC-3: Все AI-actions записываются в audit log с source=AI
- AC-4: AI не имеет прямого доступа к БД (только через Command API)

**US-AI-04**
Как Indie Hacker, я хочу попросить AI проанализировать мои расходы и дать рекомендации.

Acceptance Criteria:
- AC-1: AI получает anonymized spending data (не raw transactions с PII)
- AC-2: Ответ: текстовый анализ + конкретные рекомендации
- AC-3: AI не может создавать транзакции автоматически

---

### 1.13 Домен: Notes + RAG

**US-NOTE-01**
Как Knowledge Worker, я хочу создавать заметки с rich text, чтобы хранить знания.

Acceptance Criteria:
- AC-1: Редактор: bold/italic/headers/lists/code blocks (Markdown-совместимый)
- AC-2: Заметка: title, content, tags[], workspace_id
- AC-3: Автосохранение каждые 30 секунд (debounced)
- AC-4: История версий (последние 10 версий)

**US-NOTE-02**
Как Knowledge Worker, я хочу задать вопрос по своим заметкам и получить ответ от AI.

Acceptance Criteria:
- AC-1: RAG: заметки индексируются через pgvector embeddings
- AC-2: Вопрос → поиск релевантных chunks → LLM ответ с источниками
- AC-3: Ответ содержит ссылки на конкретные заметки (citations)
- AC-4: Поиск ограничен заметками текущего workspace (tenant isolation)

**US-NOTE-03**
Как пользователь, я хочу привязать заметку к задаче или проекту, чтобы сохранять контекст.

Acceptance Criteria:
- AC-1: Note может иметь linked_task_id или linked_project_id
- AC-2: Задача/проект показывает количество прикреплённых заметок
- AC-3: Клик по задаче → открывает связанные заметки во вкладке

**US-NOTE-04**
Как пользователь, я хочу искать по заметкам полнотекстовым поиском.

Acceptance Criteria:
- AC-1: Full-text search через PostgreSQL tsvector
- AC-2: Результаты с подсвеченными совпадениями (highlight)
- AC-3: Поиск ≤ 500ms для 10k заметок

---

## 2. USE CASES (ДЕТАЛЬНЫЕ)

### UC-QA: Quick Add — Полный Flow с Парсером

Actors: Пользователь, NLP Parser Service, Command API
Pre-conditions: Пользователь аутентифицирован, выбран workspace
Post-conditions: Сущность создана в БД, UI обновлён

Main Flow:
1. Пользователь открывает Quick Add (Cmd+K или кнопка)
2. Пользователь вводит текст (например: "Подготовить отчёт !1 #Work пт")
3. UI отправляет текст в /api/v1/parse (POST, debounce 300ms)
4. Parser извлекает: title, priority, project, due_date, type
5. Parser возвращает ParsedEntity JSON
6. UI показывает Preview карточку (< 200ms после ввода)
7. Пользователь нажимает Enter или кнопку "Добавить"
8. UI отправляет POST /api/v1/tasks
9. API создаёт Task, возвращает task_id
10. UI показывает toast с кнопкой Undo (5 сек)
11. Views обновляются (invalidate TanStack Query cache)

Alternative Flows:
- A1 (Undo): DELETE /api/v1/tasks/{id} → soft delete
- A2 (Тип = Расход): POST /api/v1/transactions
- A3 (Ошибка парсера): создаётся Inbox Item без структуры
- A4 (Ошибка API): rollback, toast, данные в localStorage

Business Rules: BR-TASK-001 (status=BACKLOG), BR-TENANT-001 (workspace_id из session)

---

### UC-TODAY: Today Dashboard — Агрегация Данных

Actors: Пользователь, Aggregation Service
Pre-conditions: Пользователь аутентифицирован

Main Flow:
1. Frontend: GET /api/v1/dashboard/today
2. Backend (параллельно):
   a. Tasks WHERE due_date = today AND workspace_id = :wid
   b. Overdue: WHERE due_date < today AND status NOT IN (DONE, CANCELLED, ARCHIVED)
   c. Events WHERE date = today AND workspace_id = :wid
   d. Finance: SUM(amount) WHERE date = today
   e. Budget: daily_limit WHERE workspace_id = :wid
3. Агрегация → DashboardDTO
4. Redis cache TTL 30 сек (key: dashboard:today:{user_id})
5. Frontend рендерит виджеты

КЛЮЧЕВОЕ: Нет отдельной таблицы Today — только агрегация из доменных таблиц.

Alt A1 (Cache hit): Redis → latency < 50ms
Alt A2 (WebSocket): изменение домена → invalidate cache + WS event

---

### UC-TASK: Task Lifecycle — State Machine

State Machine (допустимые переходы):
- BACKLOG → TODO, CANCELLED
- TODO → IN_PROGRESS, BACKLOG, CANCELLED
- IN_PROGRESS → DONE, TODO, CANCELLED
- DONE → ARCHIVED, IN_PROGRESS (reopen)
- CANCELLED → ARCHIVED, BACKLOG (restore)
- ARCHIVED → (terminal, нет переходов)

Запрещённые переходы → 422 Unprocessable Entity

DONE action:
- SET completed_at = NOW()
- IF recurring: Celery спавнит следующий экземпляр
- IF incomplete subtasks: warning (не блокировка)

CANCELLED action:
- IF incomplete subtasks: подтверждение
- SET cancelled_at = NOW()

Overdue (computed, not status):
- condition: due_date < CURRENT_DATE AND status NOT IN (DONE, CANCELLED, ARCHIVED)
- virtual field в API response, не хранится в БД

---

### UC-GCAL: Google Calendar Sync

PHASE 1 — Первичная синхронизация:
1. OAuth 2.0 → access_token + refresh_token (encrypted AES-256-GCM)
2. Celery task: full_sync(user_id)
3. GET /calendars/list → GET /events (pageToken pagination)
4. Upsert в local DB (google_event_id = unique key)
5. Сохраняется syncToken для incremental sync

PHASE 2 — Регистрация Webhook:
6. POST /calendars/{id}/events/watch → push channel
7. channelId + resourceId → БД
8. Renew job за 24ч до истечения (TTL ≤ 7 дней)

PHASE 3 — Incremental sync (webhook):
9. Google POST /api/v1/webhooks/google-calendar
10. Validate X-Goog-Channel-Token
11. GET /events?syncToken={token} → upsert/soft-delete
12. Обновить syncToken

PHASE 4 — Two-way (Personal OS → Google):
13. Создание event → local DB
14. Celery: create_google_event(event_id)
15. POST → получаем google_event_id → сохраняем

Conflict: Personal OS wins + уведомление пользователю
Business Rules: encrypted token, idempotent webhooks, soft delete

---

### UC-FIN: Expense Capture (Web + Telegram)

WEB FLOW:
1. Quick Add → тип "Расход", ввод текста
2. Parser: amount_minor, category (ML-классификация по keyword)
3. POST /api/v1/transactions {type: EXPENSE, amount_minor, currency, category_id}
4. posted=True (immutable)
5. Budget check → async notification при 80%/100%

TELEGRAM FLOW:
1. Пользователь: "кофе 250р"
2. Telegram Webhook → TelegramHandler.dispatch
3. NLP: type=EXPENSE, amount=25000 minor units, category=Food
4. POST /api/v1/transactions (через Command API)
5. Бот: "Расход: Кофе — 250 руб (Еда) | [Исправить] [Удалить]"
6. "Удалить" → reversal transaction (не физический DELETE)

Business Rules:
- BR-FIN-001: INTEGER minor units (никогда FLOAT)
- BR-FIN-002: posted=True immutable
- BR-FIN-003: correction только через reversal

---

### UC-TG: Telegram Capture — One Update → One Command

Pre-conditions: telegram_user_id привязан к user_id

Flow:
1. Telegram POST /api/v1/telegram/webhook
2. Validate X-Telegram-Bot-Api-Secret-Token
3. Lookup telegram_user_id → user_id
4. Dedup: message_id уже обработан? → ignore
5. Command Dispatcher определяет intent (ровно один)
6. Выполняется одна команда через Command API
7. sendMessage ответ пользователю
8. message_id → processed_messages (TTL 7 дней)

Правило: один update → одна команда → один результат
Повторная доставка → тот же кешированный ответ (idempotency)

---

### UC-AI: AI Planning — Preview → Confirm → Apply

Flow:
1. POST /api/v1/ai/schedule-preview
2. AI Service собирает контекст (без PII):
   - Tasks: today + overdue + high priority (titles + dates, no emails/names)
   - Calendar: free/busy slots today
   - Preferences: work hours
3. LLM генерирует Actions JSON:
   [{"action": "create_time_block", "task_id": "...", "start": "09:00", "end": "10:30"}]
4. Response: AISchedulePreview {proposed_blocks, reasoning, conflicts}
5. Frontend: Preview (drag-to-edit разрешён до confirm)
6. "Применить" → POST /api/v1/ai/schedule-apply {preview_id}
7. Policy Engine валидирует каждый action:
   - Не пересекает существующие events
   - В рамках work_hours пользователя
   - Не превышает дневной capacity
8. Command API создаёт Time Blocks
9. audit_log {source: "ai", actor_id: user_id}

Alt A1: Policy Reject → частичное применение + уведомление
Alt A2: LLM Error → graceful degradation, сообщение об ошибке
Alt A3: Пользователь редактирует preview → apply изменённый план

Business Rules:
- BR-AI-001: AI не имеет прямого доступа к БД
- BR-AI-002: Preview → explicit confirm required
- BR-AI-003: Все AI actions → audit_log
- BR-AI-004: PII не передаётся в LLM

---

## 3. BUSINESS RULES

### BR-TASK: Task Domain

| ID | Rule |
|---|---|
| BR-TASK-001 | Новая задача создаётся со статусом BACKLOG |
| BR-TASK-002 | Переходы статусов строго по state machine; невалидный переход → 422 |
| BR-TASK-003 | overdue — вычисляемое поле: due_date < today AND status NOT IN (DONE, CANCELLED, ARCHIVED). Не хранится в БД. |
| BR-TASK-004 | При переводе в DONE → completed_at = NOW() |
| BR-TASK-005 | Вложенность subtasks максимум 2 уровня (task → subtask) |
| BR-TASK-006 | Recurring task: при DONE → Celery task спавнит следующий экземпляр |
| BR-TASK-007 | Удаление задачи — soft delete (deleted_at = NOW()); физически не удаляется |
| BR-TASK-008 | Задача всегда привязана к workspace (workspace_id NOT NULL) |

### BR-FINANCE: Finance Domain

| ID | Rule |
|---|---|
| BR-FIN-001 | Денежные суммы хранятся как INTEGER minor units (копейки/центы). НИКОГДА FLOAT. |
| BR-FIN-002 | posted=True транзакция immutable. Исправление — только через reversal |
| BR-FIN-003 | Удаление транзакции запрещено. Только reversal + audit record |
| BR-FIN-004 | Баланс счёта = initial_balance + SUM(income) - SUM(expense), on-the-fly |
| BR-FIN-005 | Transfer = 2 транзакции (debit + credit), linked transfer_id |
| BR-FIN-006 | Currency всегда явная (ISO 4217) |
| BR-FIN-007 | Budget overrun не блокирует транзакцию — только уведомление |

### BR-CALENDAR: Calendar Domain

| ID | Rule |
|---|---|
| BR-CAL-001 | Kanban — view над Task.status. Нет отдельной таблицы kanban_cards |
| BR-CAL-002 | Calendar — view над Events + Tasks с due_date. Нет дублирования данных |
| BR-CAL-003 | Google Event синхронизируется через google_event_id (unique key) |
| BR-CAL-004 | Конфликт sync → Personal OS wins; пользователь уведомлён |
| BR-CAL-005 | Google refresh_token хранится encrypted (AES-256-GCM); никогда в логах |
| BR-CAL-006 | Удалённое в Google событие → soft delete в Local DB |
| BR-CAL-007 | Webhook обрабатывается idempotently |

### BR-AI: AI Domain

| ID | Rule |
|---|---|
| BR-AI-001 | AI не имеет прямого доступа к БД. Все write actions — через Policy Engine → Command API |
| BR-AI-002 | Preview → explicit Confirm required. Автоматического применения нет |
| BR-AI-003 | Все AI actions записываются в audit_log с source=ai |
| BR-AI-004 | LLM промпт не содержит PII (email, full_name, phone) |
| BR-AI-005 | AI recommendations не могут отменять posted финансовые транзакции |
| BR-AI-006 | Rate limit: 10 requests/minute per user |

### BR-TENANT: Multi-tenancy

| ID | Rule |
|---|---|
| BR-TENANT-001 | Все доменные сущности содержат workspace_id (NOT NULL) |
| BR-TENANT-002 | Все API endpoints фильтруют данные по workspace_id из auth context |
| BR-TENANT-003 | Cross-workspace доступ запрещён (403) |
| BR-TENANT-004 | Индексы БД включают workspace_id как первый столбец |

### BR-TELEGRAM: Telegram Bot

| ID | Rule |
|---|---|
| BR-TG-001 | Один Telegram update → ровно одна команда (no fan-out) |
| BR-TG-002 | Все команды через Command API (не прямой SQL) |
| BR-TG-003 | Idempotency: message_id хранится 7 дней |
| BR-TG-004 | Webhook secret token валидируется на каждом запросе |
| BR-TG-005 | Revoke очищает telegram_user_id, не удаляет данные |

### BR-AUDIT: Audit Trail

| ID | Rule |
|---|---|
| BR-AUDIT-001 | Все write операции записываются в audit_log |
| BR-AUDIT-002 | audit_log immutable (нет UPDATE/DELETE) |
| BR-AUDIT-003 | source: "user" or "ai" or "system" or "telegram" or "google_sync" |

---

## 4. ACCEPTANCE CRITERIA МАТРИЦА

| UC | AC | Priority | MVP |
|---|---|---|---|
| UC-QA | Cmd+K Quick Add с любой страницы | P0 | Да |
| UC-QA | Парсер дат (4+ форматов) | P0 | Да |
| UC-QA | Парсер приоритета (!1/!2/!3) | P0 | Да |
| UC-QA | Парсер проекта (#Name) | P1 | Да |
| UC-QA | Preview < 200ms | P1 | Да |
| UC-QA | Undo 5-секундное окно | P2 | Да |
| UC-QA | Fallback → Inbox Item | P1 | Да |
| UC-TODAY | Dashboard ≤ 2 сек | P0 | Да |
| UC-TODAY | Нет хранилища Today (агрегация) | P0 | Да |
| UC-TODAY | Redis cache TTL 30 сек | P1 | Да |
| UC-TODAY | WebSocket обновление | P1 | Да |
| UC-TODAY | Overdue + today tasks + events + finance | P0 | Да |
| UC-TASK | State machine 422 при невалидном переходе | P0 | Да |
| UC-TASK | completed_at при DONE | P0 | Да |
| UC-TASK | Overdue = computed field (не статус) | P0 | Да |
| UC-TASK | Soft delete | P0 | Да |
| UC-TASK | Subtasks макс 2 уровня | P1 | Да |
| UC-TASK | Recurring: следующий экземпляр при DONE | P1 | Да |
| UC-TASK | workspace_id NOT NULL | P0 | Да |
| UC-GCAL | OAuth + encrypted refresh_token | P0 | Да |
| UC-GCAL | Full sync при подключении | P0 | Да |
| UC-GCAL | Webhook ≤ 5 сек | P0 | Да |
| UC-GCAL | Incremental sync fallback 15 мин | P1 | Да |
| UC-GCAL | Two-way sync | P0 | Да |
| UC-GCAL | Soft delete при Google-удалении | P0 | Да |
| UC-GCAL | Webhook idempotency | P1 | Да |
| UC-GCAL | syncToken для incremental | P0 | Да |
| UC-FIN | amount INTEGER minor units | P0 | Да |
| UC-FIN | posted=True immutable | P0 | Да |
| UC-FIN | Correction через reversal | P0 | Да |
| UC-FIN | Category auto-detection | P1 | Да |
| UC-FIN | Budget alert 80% и 100% | P1 | Да |
| UC-FIN | Telegram capture через Command API | P0 | Да |
| UC-TG | Один update → одна команда | P0 | Да |
| UC-TG | Idempotency через message_id | P0 | Да |
| UC-TG | Webhook secret validation | P0 | Да |
| UC-TG | Команды через Command API | P0 | Да |
| UC-TG | Binding via deeplink + one-time token | P0 | Да |
| UC-AI | Preview → explicit confirm | P0 | Да |
| UC-AI | AI через Policy Engine | P0 | Да |
| UC-AI | Audit log source=ai | P0 | Да |
| UC-AI | PII не в LLM | P0 | Да |
| UC-AI | Rate limit 10 req/min | P1 | Да |
| UC-AI | Graceful degradation при LLM ошибке | P1 | Да |
| UC-AI | Частичное применение (post-MVP) | P2 | Нет |

---

## FINDINGS

1. Kanban = Task View: Нет отдельной таблицы Kanban Cards. Колонки = Task.status. Drag & drop меняет статус.
2. Today Dashboard = Aggregation: Нет отдельной таблицы Today. Только агрегация из Tasks/Calendar/Finance.
3. Money = Integer: Все финансовые суммы — INTEGER minor units. Float категорически запрещён.
4. Overdue = Computed: Не хранится в БД, вычисляется в каждом запросе/response.
5. AI Gate: AI → Policy Engine → Command API. Нет прямого доступа к БД.
6. Idempotency everywhere: TG webhooks, Google webhooks, Quick Add Undo — все через dedup/idempotency keys.
7. Soft deletes only: Нет физического DELETE для транзакций, задач (audit trail preservation).
8. Tenant isolation: workspace_id в каждой сущности + в каждом index.

---

## VALIDATION

- Все User Stories (65 шт.) проверены на соответствие MVP Scope из 01-product-discovery-manager.md
- 13 доменов соответствуют зафиксированному MVP
- Business Rules консистентны между собой (нет противоречий)
- AC-матрица покрывает все 7 Use Cases
- Конфликтов с документом 01 не обнаружено

---

## EVIDENCE

- Прочитан файл: docs/it-company/01-product-discovery-manager.md (107 строк)
- MVP Scope проверен — все 13 доменов покрыты User Stories
- Tech stack (Next.js + FastAPI + PostgreSQL + Redis + Celery) учтён в UC описаниях
- Business Rules совместимы со стеком и MVP Scope

---

## CHANGED_FILES
- docs/it-company/02-business-analyst.md (создан)

---

## REMAINING_ISSUES
- OpenAPI schema — задача для роли 03-system-architect
- ERD — задача для Database Architect
- Wireframes — задача для UX Designer

---

## BLOCKERS
- Нет блокеров

---

## DECISIONS

| # | Решение | Обоснование |
|---|---|---|
| D-01 | Kanban = view над Task.status | Из 01-pd; избегает дублирования данных |
| D-02 | Money = INTEGER minor units | Точность; стандарт финтех |
| D-03 | Overdue = computed field | Статус дискретный; overdue непрерывное условие |
| D-04 | AI → Policy Engine | Безопасность; audit trail |
| D-05 | Google Sync: Personal OS wins | Простота; предсказуемость |
| D-06 | Soft deletes везде | Audit trail; GDPR compliance |
| D-07 | TG: one update → one command | Предсказуемость; idempotency |

---

## HANDOFF

Следующему агенту (03-system-architect):
- 65 User Stories по 13 доменам с Acceptance Criteria
- 7 Use Cases (UC-QA, UC-TODAY, UC-TASK, UC-GCAL, UC-FIN, UC-TG, UC-AI)
- Business Rules по доменам (Task, Finance, Calendar, AI, Tenant, Telegram, Audit)
- AC-матрица с Priority (P0/P1/P2) и MVP-флагами
- Ключевые ограничения:
  - Kanban = Task view (нет kanban_cards таблицы)
  - Money = INTEGER minor units
  - Overdue = computed (не в БД)
  - AI = Policy Engine gate
  - workspace_id в каждой сущности
  - Soft deletes везде

## NEXT_AGENT: 03-system-architect
"""

with open("docs/it-company/02-business-analyst.md", "w", encoding="utf-8") as f:
    f.write(content)

print("File written successfully")
print(f"Size: {len(content)} bytes")
