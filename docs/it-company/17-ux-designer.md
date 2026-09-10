# 17 — UX Designer

STATUS: VERIFIED
TASK: Разработать UX-документацию для Personal OS — User Flows, Wireframe-описания, Information Architecture, UX-принципы
INPUT: docs/it-company/01-product-discovery-manager.md — Product Vision, MVP Scope, пользовательские сегменты, технологический стек

---

## ACTIONS

1. Изучен документ 01-product-discovery-manager.md
2. Определены ключевые user flows (6 flows)
3. Описаны wireframes для 6 экранов + Telegram Bot patterns
4. Сформирована Information Architecture (Sidebar, Mobile, Page Hierarchy)
5. Сформулированы 7 UX-принципов для Personal OS

---

## CHANGED_FILES

- `docs/it-company/17-ux-designer.md`

---

## FINDINGS

- Ключевой принцип из Discovery: Kanban, Dashboard, Calendar — разные представления одной и той же сущности, не отдельные хранилища. UX должен делать это очевидным.
- Quick Add <= 3 действия — жёсткое требование из MVP Scope.
- Morning Brief — расчётный продукт + AI-комментарий, не просто список задач.
- Telegram Bot — это не отдельная БД, а capture-канал в единое ядро.
- AI flows всегда требуют Preview -> Confirm/Reject перед изменением данных.

---

## DECISIONS

- ASCII-диаграммы вместо Mermaid для максимальной переносимости в MD-файлах
- Wireframes описаны словесно с координатной структурой (Top/Left/Center/Right/Bottom)
- IA описана через трёхуровневую иерархию: L1 (Sidebar) -> L2 (секции) -> L3 (детали)
- Mobile navigation использует Bottom Tab Bar из 5 элементов (PWA pattern)

---

## 1. USER FLOW ДИАГРАММЫ

---

### 1.1 Quick Add Flow

Три параллельных сценария от единой точки входа.

```
QUICK ADD ENTRY POINT:
  [+] Button (Sidebar FAB)  /  Keyboard Shortcut [Cmd+K]
               |
       +---------------+
       | Quick Add     |
       | Modal Opens   | <- autofocus text input
       +------+--------+
              |
      User types text; AI parses intent in real-time
              |
   +----------+------------------+
   | AI detects entity type:     |
   |  [Task] [Event] [Expense]   | <- user can override
   +----------+------------------+
              |
   +----------+----------------------------+
   |          |                            |
   v          v                            v
 TASK       EVENT                     EXPENSE

SCENARIO A: TASK
[1] User types: "Написать отчёт до пятницы #work !high"
[2] AI Preview:
    Title:    "Написать отчёт"
    Deadline: пятница
    Project:  #work
    Priority: !high
[3] User presses [Enter] or [Create Task]
[4] Task created -> Toast + link to task detail
[5] Today Dashboard updates if deadline=today
[Actions: 1 input + 1 confirm = 2 actions]

SCENARIO B: EVENT
[1] User types: "Встреча с командой завтра в 14:00 на 1 час"
[2] AI Preview:
    Title: "Встреча с командой"
    Date:  tomorrow
    Time:  14:00-15:00
    Calendar: Personal (default)
[3] If slot taken -> Warning before save
[3a] User: [Keep] [Change time] [Cancel]
[4] Event created -> Google Calendar sync (if connected)
[5] Calendar View updates
[Actions: 1 input + 1 confirm = 2 actions]

SCENARIO C: EXPENSE
[1] User types: "500р кофе"
[2] AI Preview:
    Amount:   500 RUB
    Category: Food & Drinks (AI-predicted 87%)
    Account:  Cash (default)
    Date:     today
[3] User can change Category (optional dropdown)
[4] [Save Expense] -> Finance ledger updates
[5] Budget alert if limit exceeded
[Actions: 1 input + 1 confirm = 2 actions]
```

---

### 1.2 Today Dashboard Flow — Morning Start

```
USER OPENS APP (morning)
         |
         v
 +-----------------+
 | Today Dashboard |
 | auto-loaded     |
 +--------+--------+
          |
          v
 +--------------------------------------------+
 |           MORNING BRIEF CARD               |
 | "Сегодня 4 задачи, 2 встречи.              |
 |  Рекомендую начать с [task X]"             |
 |  [View Full Brief]   [Dismiss]             |
 +-------------------+------------------------+
                     |
           +---------+---------+
           |                   |
   [View Full Brief]       [Dismiss]
           |                   |
           v                   v
 +------------------+  Dashboard shows:
 | Morning Brief    |  - Today tasks (by priority)
 | Detail Modal     |  - Today events (timeline)
 |  - Task list     |  - Budget status
 |  - Calendar      |  - Overdue items
 |  - AI insights   |
 |  [Start Day]     |
 +--------+---------+
          |
          v
 USER INTERACTS WITH DASHBOARD
          |
   +------+------------------+
   v      v                  v
[Click  [Mark task       [Open
 event]  complete]        Finance]
   |      |                  |
   v      v                  v
Calendar  Task.status     Finance
 Detail   updates in      Overview
          ALL views simultaneously
          (Today + Kanban + Task List)
```

---

### 1.3 Task Lifecycle Flow

```
               +-----------+
               |  CREATED  | <- Quick Add / Telegram / AI Capture
               +-----+-----+
                     |
          +----------v----------+
          | INBOX (no project)  | <- default state
          +----------+----------+
                     | User assigns project/deadline
                     v
               +-----------+
               |  BACKLOG  | <- in project, no date
               +-----+-----+
                     | User or AI schedules
                     v
               +-----------+
               | SCHEDULED | <- has date/time block
               +-----+-----+
                     | Date arrives -> auto-moved
                     v
               +------------+
               | IN PROGRESS| <- user starts / drag Kanban
               +-----+------+
                +----+----+
                v         v
          +--------+  +--------+
          |  DONE  |  |BLOCKED |
          +----+---+  +----+---+
               |           | User resolves -> back to IN PROGRESS
               v
         +-----------+
         | ARCHIVED  | <- auto after 30d DONE / manual
         +-----------+

RULES:
- Kanban columns = Task.status (not a separate table)
- Today Dashboard: Scheduled(today) + IN PROGRESS
- Overdue = Scheduled with past date -> red badge
- Recurring: DONE creates next instance automatically
- Subtasks: DONE only if all subtasks DONE
```

---

### 1.4 Expense Capture (Telegram Bot)

```
User: "500р кофе"
         |
         v
 +------------------------------------------+
 | BOT PROCESSING                           |
 | NLP: amount=500, currency=RUB            |
 | Category prediction: Food (87%)          |
 +------------------+-----------------------+
                    |
                    v
 Bot reply:
 +------------------------------------------+
 | Расход зафиксирован                      |
 | Сумма:    500 RUB                        |
 | Категория: Еда и напитки                 |
 | Счёт:     Наличные                       |
 | Дата:     сегодня                        |
 |                                          |
 | [Ok] [Изменить] [Отмена]                 |
 +------------------------------------------+
       |
   +---+------------------+
   v   v                  v
 [Ok] [Edit]          [Cancel]
   |     |                |
   v     v                v
 Saved  Bot shows      Nothing
   |    category       created
   v    keyboard
 "Сохранено!"
       |
       v (user picks category)
 Saved with corrected category
       |
       v
 Finance ledger updated;
 Web dashboard reflects change
```

---

### 1.5 Google Calendar Connect Flow

```
Settings -> Integrations -> Google Calendar -> [Connect]
      |
      v
 INFO SCREEN:
 +------------------------------------------+
 | Подключение Google Calendar              |
 | - Sync Google -> Personal OS            |
 | - Sync Personal OS -> Google            |
 | - Two-way (webhook)                     |
 | Permissions: calendar.events            |
 |                                         |
 | [Continue]  [Cancel]                    |
 +------------------------------------------+
      |
      v
 STEP 2: OAUTH REDIRECT
 Browser -> Google OAuth Consent Screen
      | User grants permission
      v
 Redirect back -> callback URL
      |
      v
 STEP 3: TOKEN EXCHANGE (backend)
 FastAPI: code -> access_token + refresh_token
 Stored encrypted in DB
      |
      v
 STEP 4: FIRST SYNC
 +------------------------------------------+
 | Найдено календарей: 3                    |
 | [ ] Personal                             |
 | [ ] Work                                 |
 | [ ] Birthdays                            |
 | [Sync Selected]  [Sync All]              |
 +------------------------------------------+
      | Celery job starts
      v
 Progress: "Импортировано 47 / 230..."
      |
      v DONE
 +------------------------------------------+
 | Google Calendar подключён               |
 | Импортировано: 230 событий              |
 | [Перейти в Calendar] [Настройки sync]   |
 +------------------------------------------+

ERRORS:
 - Permission denied -> "Необходимо разрешение. [Повторить]"
 - Sync conflict -> "2 конфликта. [Разрешить]"
 - Token expired -> silent background refresh
```

---

### 1.6 AI Planning Flow

```
TRIGGER: Dashboard [AI Plan My Day] / Task List [AI Schedule]

User clicks [AI Plan My Day]
      |
      v
 "AI анализирует... (2-4 sec)"
 (tasks, meetings, work hours, energy pattern)
      |
      v
 AI PREVIEW MODAL (required step):
 +------------------------------------------+
 | AI предлагает план:                      |
 |                                          |
 | 09:00-10:30  Написать отчёт [!high]      |
 | 10:30-11:00  Перерыв                     |
 | 11:00-12:00  Team Sync                   |
 | 12:00-13:00  Обед                        |
 | 13:00-14:30  Code review PR #42          |
 | 15:00-16:00  Client Call                 |
 | 16:00-17:30  Написать тесты              |
 |                                          |
 | WARN: "Задача [X] -> завтра"             |
 |                                          |
 | [Применить план]                         |
 | [Редактировать]                          |
 | [Отклонить]                              |
 +------------------------------------------+
       |
   +---+-------------------+
   v   v                   v
 [OK] [Edit]           [Reject]
   |     |                 |
   v     v                 v
 Time  Inline edit    Nothing changed
 Blocks plan ->       (no side effects)
 created [Apply edited]
   |         |
   v         v
 Calendar Plan applied with edits
 updated
```

---

## 2. WIREFRAME ОПИСАНИЯ

---

### 2.1 Dashboard / Today

Стартовый экран. Агрегирует задачи на сегодня, события, бюджет, AI Brief.

```
LAYOUT (desktop):
+--------------------+-----------------------------------------------+
| SIDEBAR (64-240px) |           MAIN CONTENT AREA                   |
| (collapsible)      |                                               |
|                    |  TOP BAR                                      |
| [logo]             |  "Пятница, 10 сентября"     [Bell] [Settings] |
|                    |                                               |
| [Home Today] <     |  MORNING BRIEF (full width, dismissable):     |
| [Tasks]            |  "Доброе утро! 4 задачи, 2 встречи.           |
| [Calendar]         |   Рекомендую начать с [Отчёт]."              |
| [Finance]          |            [View Brief]    [Dismiss]          |
| [AI]               |                                               |
|                    |  MAIN GRID (2 columns):                       |
| ---                |  +-----------------+  +-----------------+    |
|                    |  | TODAY'S TASKS   |  | TODAY'S SCHEDULE|    |
| [Projects]         |  |                 |  |                 |    |
| [Tags]             |  | [ ] Написать    |  | 10:00 Team Sync |    |
| [Notes]            |  |   !high today   |  | 14:00 Client    |    |
|                    |  | [ ] Code review |  | 16:00 [free]    |    |
| ---                |  | [x] Standup     |  | [Open Calendar] |    |
|                    |  | [+ Add task]    |  |                 |    |
| [+ Quick Add] FAB  |  +-----------------+  +-----------------+    |
|                    |                                               |
|                    |  BOTTOM ROW (2 columns):                      |
|                    |  +-----------------+  +-----------------+    |
|                    |  | BUDGET STATUS   |  | ACTIVITY LOG    |    |
|                    |  | Spent: 12,400   |  | - Task done     |    |
|                    |  | [====----] 72%  |  | - Event added   |    |
|                    |  | [Open Finance]  |  | [View all]      |    |
|                    |  +-----------------+  +-----------------+    |
+--------------------+-----------------------------------------------+

KEY DECISIONS:
- Morning Brief = first element after TopBar, dismissable
- Task list = Today-filter of Task entity (not a separate component)
- Budget widget = summary; click -> Finance Overview
- [+ Quick Add] = FAB, always accessible
- All cards are clickable -> detail slide-over
```

---

### 2.2 Quick Add (Modal)

```
+---------------------------------------------------------------------+
|                    OVERLAY (backdrop blur)                           |
|                                                                     |
|   +---------------------------------------------------------------+ |
|   | Quick Add                                           [Esc / X] | |
|   |                                                               | |
|   | +-----------------------------------------------------------+ | |
|   | | Напиши задачу, событие или расход...     [Mic voice input] | | |
|   | +-----------------------------------------------------------+ | |
|   |                                                               | |
|   | ENTITY TYPE (auto-detected; user can override):               | |
|   | [Task]   [Event]   [Expense]   [Note]                        | |
|   |                                                               | |
|   | AI PREVIEW (appears after >2 words typed):                    | |
|   | +-----------------------------------------------------------+ | |
|   | | AI распознал:                                             | | |
|   | |   Title:    "Написать отчёт"                             | | |
|   | |   Deadline: пятница, 13 сентября                         | | |
|   | |   Priority: Высокий                                      | | |
|   | |   Project:  #work                   [Edit details]       | | |
|   | +-----------------------------------------------------------+ | |
|   |                                                               | |
|   | DETAIL EXPANDER (hidden; opens on "Edit details"):            | |
|   | [Project v]  [Date v]  [Tag v]  [Priority v]                 | |
|   |                                                               | |
|   |                          [Create Task]   [Cancel]            | |
|   +---------------------------------------------------------------+ |
+---------------------------------------------------------------------+

KEY DECISIONS:
- Opens < 100ms; autofocus on text input
- AI preview appears while typing (non-blocking)
- Detail expander hidden by default (<=3 actions rule)
- Enter = Create; Escape = Cancel (no creation)
```

---

### 2.3 Tasks List + Kanban

One URL, view switcher (List | Kanban).

```
LIST VIEW:
+---------------------------------------------------------------------+
| Tasks                  [Search]  [Filter v]  [List | Kanban]        |
|                                                                     |
| [All] [Today] [Week] [Overdue] [No Date]   Project: [All v]        |
|                                                                     |
| [ ] Написать отчёт        #work    Fri   !HIGH   [...]             |
| [ ] Code review PR #42    #work    Wed   !MED    [...]             |
| [ ] Купить продукты       personal Today !LOW    [...]             |
| [x] Daily standup         #work    done          [...]             |
|                                                                     |
| [+ Добавить задачу]  (inline add, not a modal)                      |
+---------------------------------------------------------------------+

KANBAN VIEW:
+---------------------------------------------------------------------+
| Tasks                  [Search]  [Filter v]  [List | Kanban]        |
|                                                                     |
| +----------+  +----------+  +----------+  +----------+            |
| |  INBOX   |  | IN PROG. |  |  DONE    |  | BLOCKED  |            |
| |  (4)     |  |  (2)     |  |  (7)     |  |  (1)     |            |
| +----------+  +----------+  +----------+  +----------+            |
| | Написать |  | Code rev |  | Standup  |  | PR #42   |            |
| | отчёт    |  | PR#42    |  | (done)   |  | (waiting)|            |
| | !HIGH    |  | #work    |  |          |  |          |            |
| +----------+  +----------+  +----------+  +----------+            |
| | [+ Add]  |                                                       |
| +----------+                                                       |
|                                                                     |
| Drag & Drop -> PATCH /tasks/{id} {status} via WebSocket            |
+---------------------------------------------------------------------+

KEY DECISIONS:
- Task.status drives both Kanban column and List filter
- View switch = client-side state, no reload
- Filters stored in URL query params
```

---

### 2.4 Calendar (Day/Week View)

```
+---------------------------------------------------------------------+
| September 2026  [< Prev]  [Today]  [Next >]  [Day | Week | Month]  |
|                                                                     |
| WEEK GRID:                                                          |
|       | Mon 8  | Tue 9  | Wed 10 | Thu 11 | Fri 12 | Sat 13 |     |
| ------+--------+--------+--------+--------+--------+--------+     |
|  9:00 |        |        |[======]|        |        |        |     |
|       |        |        |Team    |        |        |        |     |
| 10:00 |        |[======]|Sync    |        |        |        |     |
|       |        |[Task   |        |        |        |        |     |
|       |        |Block]  |        |        |        |        |     |
| 12:00 |        |        |        |        |        |        |     |
| 14:00 |        |        |        |[======]|        |        |     |
|       |        |        |        |Client  |        |        |     |
|       |        |        |        |Call    |        |        |     |
|                                                                     |
| MINI CALENDAR (right panel):   UPCOMING (right panel):             |
| [mini month grid]              - Tomorrow: Standup 10:00           |
|                                - Thu: Client Call 14:00            |
| CALENDARS:                     - Fri: Sprint Review 16:00          |
| [x] Personal (blue)                                                 |
| [x] Work (green)                                                    |
| [x] Google Calendar (red)                                           |
| [x] Time Blocks (purple)                                            |
|                                                                     |
| Click empty slot -> Quick Add Event (pre-filled date/time)         |
| Drag event bottom edge -> resize duration                           |
+---------------------------------------------------------------------+
```

---

### 2.5 Finance Overview

```
+---------------------------------------------------------------------+
| Finance                          [+ Add]   [Period: Sept v]        |
|                                                                     |
| SUMMARY ROW (full width):                                           |
| +---------------+  +---------------+  +-------------------+        |
| | Balance       |  | Income        |  | Expenses          |        |
| | 127,600 RUB   |  | 50,000 RUB    |  | 22,400 RUB        |        |
| | (all accounts)|  | this month    |  | this month        |        |
| +---------------+  +---------------+  +-------------------+        |
|                                                                     |
| BUDGET BARS (color: green<70% / yellow 70-90% / red >90%):         |
| Food:        [========--]  8000 / 10000 (80%)                      |
| Transport:   [====------]  2000 / 5000  (40%)                      |
| Entertain.:  [=========!]  4500 / 5000  (90%) WARNING              |
| Health:      [===-------]  1500 / 5000  (30%)                      |
|                                                                     |
| ACCOUNTS (left):               RECENT TRANSACTIONS (right):        |
| +--------------------+         +-----------------------------+     |
| | Debit card: 45,200 |         | Today                       |     |
| | Cash:       12,400 |         | Coffee        -500 RUB      |     |
| | Savings:    70,000 |         | Groceries    -2300 RUB      |     |
| |                    |         | Salary      +50000 RUB      |     |
| | [+ Add account]    |         | [Show all]                  |     |
| +--------------------+         +-----------------------------+     |
|                                                                     |
| CHART (bottom, full width):                                         |
| [Bar chart: daily spending this month]                              |
| [By day | By category | By account]                                |
+---------------------------------------------------------------------+
```

---

### 2.6 Telegram Bot Conversation Patterns

```
PATTERN 1: EXPENSE CAPTURE
User: "500р кофе"
Bot:  Расход зафиксирован
      Сумма:    500 RUB
      Категория: Еда и напитки
      Счёт:     Наличные
      [Ok] [Изменить] [Отмена]

--------------------------------------------------
PATTERN 2: TASK CREATE
User: "задача: позвонить клиенту завтра в 10"
Bot:  Задача создана:
      "Позвонить клиенту"
      Завтра, 10:00
      [Открыть в приложении]

--------------------------------------------------
PATTERN 3: MORNING BRIEF
User: /brief
Bot:  Доброе утро! Твой план:

      Задачи (4):
      * Написать отчёт (!HIGH, дедлайн сегодня)
      * Code review PR #42
      * Купить продукты
      * Ответить на письма

      Встречи:
      * 11:00 Team Sync (1ч)
      * 14:00 Client Call (30мин)

      Бюджет: 72% месяца использовано
      Совет: "Начни с отчёта — дедлайн сегодня."

--------------------------------------------------
PATTERN 4: BALANCE CHECK
User: /balance
Bot:  Текущий баланс:
      Карта:      45,200 RUB
      Наличные:   12,400 RUB
      Сбережения: 70,000 RUB
      ──────────────────────
      Всего:     127,600 RUB

--------------------------------------------------
PATTERN 5: ONBOARDING
User: /start
Bot:  Привет! Я Personal OS Bot.

      Что умею:
      * "500р кофе" -> записать расход
      * "задача: [текст]" -> создать задачу
      * /brief -> утренний брифинг
      * /balance -> баланс счетов
      * /tasks -> задачи на сегодня

      [Открыть приложение]
```

---

## 3. INFORMATION ARCHITECTURE (IA)

---

### 3.1 Sidebar Navigation Structure

```
PRIMARY (L1):
  [Home]     Today / Dashboard    <- default start screen
  [Tasks]    List + Kanban
  [Calendar] day/week/month
  [Finance]  accounts, expenses, budgets
  [AI]       chat + planning + insights

SECONDARY (L2):
  [Projects]
      Work
      Personal
      [+ New Project]
  [Tags]     cross-cutting labels
  [Notes]    linked to tasks/projects
  [Activity] timeline, audit

UTILITIES (bottom of sidebar):
  [Settings]
  [Help]
  [Notifications]
  [Profile]
```

### 3.2 Page Hierarchy (L1 -> L2 -> L3)

```
App
|-- Today Dashboard (L1)
|   |-- Morning Brief Modal (L2)
|   |-- Task Detail slide-over (L2)
|   +-- Event Detail slide-over (L2)
|
|-- Tasks (L1)
|   |-- List View (L2, default)
|   |-- Kanban View (L2)
|   +-- Task Detail (L2)
|       |-- Subtasks (L3)
|       |-- Comments (L3)
|       |-- Activity Log (L3)
|       +-- Linked Time Blocks (L3)
|
|-- Calendar (L1)
|   |-- Day View (L2)
|   |-- Week View (L2, default)
|   |-- Month View (L2)
|   +-- Event Detail (L2)
|       |-- Attendees (L3)
|       +-- Linked Tasks (L3)
|
|-- Finance (L1)
|   |-- Overview (L2, default)
|   |-- Transactions (L2)
|   |-- Budgets (L2)
|   +-- Accounts (L2)
|       +-- Account Detail (L3)
|
|-- AI Advisor (L1)
|   |-- Chat (L2)
|   |-- Planning (L2)
|   +-- Insights (L2)
|
|-- Projects (L1)
|   |-- Project List (L2)
|   +-- Project Detail (L2)
|       |-- Tasks filtered (L3)
|       |-- Notes (L3)
|       +-- Activity (L3)
|
+-- Settings (L1)
    |-- Profile (L2)
    |-- Integrations (L2)
    |   |-- Google Calendar (L3)
    |   +-- Telegram Bot (L3)
    |-- Notifications (L2)
    |-- Appearance (L2)
    +-- Data & Backup (L2)
```

### 3.3 Mobile/PWA Navigation Patterns

```
BOTTOM TAB BAR (5 tabs, mobile):
+--------------------------------------------------+
|                [CONTENT AREA]                    |
|                                                  |
|  +--------------------------------------------+ |
|  |  Home   Tasks  [+]  Calendar   Finance     | |
|  |  Today         Add                         | |
|  +--------------------------------------------+ |
+--------------------------------------------------+

MOBILE RULES:
- Bottom Tab Bar: Today, Tasks, [+] QuickAdd (center FAB), Calendar, Finance
- AI Advisor: button in Top Bar (chat icon)
- Projects, Notes, Settings: "More" drawer / hamburger
- Sidebar desktop: collapsible (64px icons / 240px full)
- Details open as slide-over panels (context preserved)

GESTURE PATTERNS (PWA):
- Swipe right on task -> Mark done
- Swipe left on task -> Delete / More options
- Pull-to-refresh -> sync Google Calendar
- Long-press event -> context menu (edit/delete/move)

RESPONSIVE BREAKPOINTS:
- Mobile   < 768px   -> Bottom Tab Bar
- Tablet  768-1024px -> Collapsed Sidebar (icon-only) + main
- Desktop > 1024px   -> Full Sidebar + main + optional right panel
```

---

## 4. UX ПРИНЦИПЫ ДЛЯ PERSONAL OS

---

### Принцип 1: Скорость важнее полноты (Speed Over Completeness)

**Правило:** Создание любой сущности (task, event, expense) <= 3 действия от намерения до сохранения.

**Применение:**
- Quick Add: 1 нажатие + 1 текстовый ввод + 1 Enter = готово
- Детальные поля (проект, теги, дата) скрыты по умолчанию
- Quick Add доступен с любого экрана (Cmd+K глобально)
- Нет обязательной навигации перед созданием

**Антипаттерн:** Многошаговые мастера для создания задачи.

---

### Принцип 2: Один источник правды (Single Source of Truth)

**Правило:** Dashboard, Kanban, Calendar, Task List — разные представления одних данных. Изменение в одном месте мгновенно отражается везде.

**Применение:**
- Task.status -> управляет колонкой Kanban И фильтром Today И badge Sidebar
- Drag в Kanban = PATCH /tasks/{id} -> WebSocket обновляет все views
- Calendar Time Block = задача с временем, не отдельная сущность
- Никогда не показывать разные данные от точки входа

**Антипаттерн:** "Kanban cards" как отдельная таблица в БД.

---

### Принцип 3: AI всегда в режиме Preview (AI Safety First)

**Правило:** AI никогда не изменяет данные без явного подтверждения. Обязательно: Preview -> Confirm/Reject.

**Применение:**
- AI Schedule Plan -> Preview -> [Применить] или [Отклонить]
- AI Capture Telegram -> parse preview -> [Ok]
- Rejection = no side-effects, данные неизменны
- AI не создаёт/удаляет/изменяет без user action

**Антипаттерн:** AI автоматически переносит задачи или удаляет события.

---

### Принцип 4: Контекст сохраняется (Context Preservation)

**Правило:** Переход к деталям не уничтожает контекст. Детали = slide-over / modal, не полные page transitions.

**Применение:**
- Task click in Today -> slide-over справа, Dashboard остаётся видимым
- Event click in Calendar -> slide-over, сетка за панелью
- Back = закрытие slide-over, scroll position сохраняется
- Quick Add = modal overlay над любым экраном

**Антипаттерн:** Полная смена страницы при открытии Task Detail.

---

### Принцип 5: Ошибки предупреждаются (Forgiving Design)

**Правило:** Предупреждение о конфликтах ДО создания. Деструктивные действия = подтверждение + Undo.

**Применение:**
- Quick Add Event: Warning о занятом слоте до сохранения
- Delete Task: "Удалить? [Удалить] [Отмена]" + 5-сек Undo toast
- Budget overspend: уведомление при добавлении расхода, не в конце месяца
- Recurring delete: "Только эту? Или все будущие?"

**Антипаттерн:** Удаление без подтверждения. Ошибки обнаруживаются только после действия.

---

### Принцип 6: Прогрессивное раскрытие (Progressive Disclosure)

**Правило:** Интерфейс показывает только необходимое. Сложность раскрывается по запросу.

**Применение:**
- Quick Add: базовые поля видны, детали — за [Edit details]
- Finance: Summary сразу, детальные транзакции — по scroll/клику
- Settings: основные параметры сразу, экспертные — за [Advanced]

**Антипаттерн:** Форма с 15 обязательными полями при создании задачи.

---

### Принцип 7: Telegram — полноценный канал (Channel Parity)

**Правило:** Ключевые операции выполнимы полностью через Telegram без открытия Web.

**Применение:**
- Expense: capture -> AI parse -> confirm -> saved — всё в Telegram
- Task: create -> confirm — всё в Telegram
- /brief — полный контент прямо в чате
- Confirmation = Inline Keyboard (не reply keyboard)
- Ошибки — информативные сообщения, не технические коды

**Антипаттерн:** "Для подтверждения перейдите в приложение."

---

## VALIDATION

- [x] Все 6 User Flows покрывают UC из MVP Scope (01-product-discovery-manager.md)
- [x] Quick Add: подтверждено <=3 действия во всех 3 сценариях
- [x] AI flows: везде присутствует Preview -> Confirm/Reject
- [x] Telegram expense capture: полностью без выхода в Web
- [x] Google Calendar OAuth: соответствует OIDC/OAuth из стека
- [x] Task Lifecycle: статусы согласованы с Kanban (не отдельная таблица)
- [x] IA: все MVP-фичи покрыты в навигации
- [x] Mobile: Bottom Tab Bar для PWA (5 tabs)
- [x] 7 UX-принципов охватывают все критичные аспекты продукта
- [x] Конфликтов с 01-product-discovery-manager.md не обнаружено

---

## EVIDENCE

Решения основаны на 01-product-discovery-manager.md:
- "Inbox / Quick Add (<=3 действия)" -> Принцип 1 + Quick Add Flow
- "Telegram, Web не создают собственных сущностей — передают в ядро" -> Принципы 2, 7
- "AI Capture + AI Schedule Preview" -> Принцип 3 + AI Planning Flow
- "Kanban (view над Task.status, не отдельная card-таблица)" -> Принцип 2 + Task Lifecycle
- "Morning Brief (расчётный + AI-комментарий)" -> Today Dashboard Flow
- "Google Calendar two-way sync" -> Google Calendar Connect Flow
- "PWA basics" -> Mobile Navigation Patterns

---

## REMAINING_ISSUES

- Конкретные цвета, typography, spacing -> задача UI Designer
- Accessibility (ARIA, keyboard nav) -> Accessibility Auditor (роль 26a)
- Charts/graphs wireframes для Finance -> Data Visualization Engineer (роль 20a)
- AI Insights / Analytics экраны -> не детализированы в MVP Scope
- Onboarding flow (первый вход) -> не описан в MVP Scope, требует уточнения

---

## BLOCKERS

Нет блокеров. Все входные данные получены и достаточны.

---

## HANDOFF

Следующий агент получает:
1. 6 детальных User Flow диаграмм — готовы для реализации
2. Wireframe-описания 6 экранов + Telegram Bot patterns — структура определена
3. IA с трёхуровневой иерархией — готова для роутинга
4. 7 UX-принципов — обязательны для UI Designer и Frontend

Ключевые ограничения:
- Quick Add <= 3 действия — нельзя добавлять обязательные шаги
- AI всегда Preview — нельзя auto-apply без подтверждения
- Task.status = единственный источник для Kanban и Today — без отдельных таблиц
- Bottom Tab Bar на mobile — максимум 5 элементов

---

## NEXT_AGENT: 18-ui-designer
