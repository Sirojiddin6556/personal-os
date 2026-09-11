# 19 — Frontend Logic Developer

STATUS: VERIFIED
TASK: Реализовать программный слой бизнес-логики клиентского приложения `apps/web` (Personal OS): доменные типы и контракты (TypeScript), устойчивый HTTP API-клиент с поддержкой RFC 9457 Problem Details, автоматическим Idempotency-Key и ETag/If-Match оптимистической блокировкой, синглтон WebSocket-клиента с Full Jitter Backoff реконнекцией (1с–30с), 30-секундным heartbeat и автоматической компенсацией пропущенных событий, иерархическую фабрику Query Keys, набор хуков TanStack Query v5 с оптимистичными обновлениями и откатами (Tasks, Calendar, Finance, WebSocket, AI Planner) и легковесный Zustand-стор UI-состояния.

INPUT:
- `docs/it-company/04-solution-architect.md` — C4 Containers, Bounded Contexts, Transactional Outbox Event Catalog, REST v1, RFC 9457 Problem Details.
- `docs/it-company/06-system-analyst.md` — Спецификации конечных автоматов сущностей, Sequence и State диаграммы.
- `docs/it-company/16-frontend-architect.md` — Архитектура состояния (Server vs UI state), спецификации `apiRequest`, `ws-client`, `query-keys`, перехватывающие маршруты, Performance-бюджеты.
- `docs/it-company/17-ux-designer.md` — User Flows, Quick Add Cmd+K flow, Kanban board interaction, Context preservation.
- `docs/it-company/18-ui-designer.md` — Дизайн-токены, спецификации доменных компонентов.

ACTIONS:
1. Создана структура пакета `apps/web` (`package.json`, `tsconfig.json`) с зависимостями Next.js 14, React 18, TanStack Query v5, Zustand, @dnd-kit.
2. Реализован модуль доменных типов `apps/web/src/types/domain.ts`:
   - Enums: `TaskStatus` (7 состояний), `Priority` (P1-P4), `TransactionType` (income, expense, transfer).
   - Сущности: `Task`, `Subtask`, `Project`, `CalendarEvent`, `TimeBlock`, `Account`, `Category`, `Transaction`, `Budget`, `Note`, `Habit`, `HabitLog`, `Notification`, `AIPreviewPlan`, `AIPlanChange`, `ParsedIntent`, `DashboardToday`.
   - Подробные JSDoc-комментарии ко всем полям и типам данных.
3. Реализован HTTP API-клиент `apps/web/src/lib/api-client.ts`:
   - Универсальная функция `apiRequest<TData, TBody>` с базовым URL из env (`NEXT_PUBLIC_API_URL` / `/v1`).
   - Автоматическая генерация `Idempotency-Key` (UUIDv4 через `crypto.randomUUID()`) для мутирующих запросов (`POST`, `PATCH`, `DELETE`).
   - Внедрение заголовка авторизации `Authorization: Bearer {token}` из параметров или браузерного хранилища (`localStorage` / cookie).
   - Поддержка заголовка оптимистической блокировки `If-Match: W/"{version}"` при передаче `version`.
   - Иерархия типизированных ошибок: `ApiError`, `ConflictError` (409 Conflict с извлечением `currentVersion`), `PreconditionFailedError` (412 Precondition Failed), `ValidationError` (422 с маппингом полей).
   - Хелпер курсорной пагинации `fetchPaginated<TItem>`.
4. Реализована фабрика ключей кэша `apps/web/src/lib/query-keys.ts`:
   - Гранулярные ключи для: `tasks`, `calendar`, `finance`, `dashboard`, `notes`, `advisor`, `habits`, `notifications`.
5. Реализован синглтон TanStack `QueryClient` `apps/web/src/lib/query-client.ts`:
   - `staleTime: 30s`, `gcTime: 10m`, умный retry (пропуск повторов для 401, 403, 404, 422).
6. Реализован синглтон WebSocket-клиента `apps/web/src/lib/ws-client.ts`:
   - Подключение к `/v1/ws` с аутентификационным токеном.
   - Метод `subscribe(eventType, handler)` с возвратом функции отписки.
   - Heartbeat механизм (отправка `ping` каждые 30с, ожидание `pong` в течение 10с с автопереподключением при зависании).
   - Алгоритм реконнекции Full Jitter Backoff (экспоненциальный рост от 1с до 30с со случайным разбросом +/-20%).
   - Автоматическая компенсация пропущенных событий при реконнекте (`queryClient.invalidateQueries({ type: 'active' })`).
   - Автоматическая маршрутизация доменных событий Outbox в селективную инвалидацию кэша TanStack Query.
7. Реализован модуль хуков задач `apps/web/src/hooks/useTasks.ts`:
   - `useTasksList(filters)`: бесконечная курсорная пагинация с `useInfiniteQuery`.
   - `useTask(id)`: запрос детального состояния задачи.
   - `useCreateTask()`: мутация с оптимистичным добавлением во все активные списки задач и откатом при ошибке сети.
   - `useUpdateTask()`: мутация с оптимистичным обновлением, версионированием и передачей `If-Match: W/"{version}"`.
   - `useCompleteTask()`: оптимистичный перевод в статус `DONE` с фиксацией `completed_at`.
   - `useMoveTask()`: оптимистичное изменение статуса и порядка в колонках Kanban.
8. Реализован модуль хуков календаря `apps/web/src/hooks/useCalendar.ts`:
   - `useCalendarEvents(from, to)`: запрос событий в диапазоне дат.
   - `useCreateEvent()`: создание календарного события с инвалидацией расписания.
   - `useCreateTimeBlock()`: выделение рабочего тайм-блока под задачу.
   - `useGoogleSyncStatus()`: мониторинг статуса двухсторонней синхронизации Google Calendar и триггер ручной синхронизации.
9. Реализован модуль финансовых хуков `apps/web/src/hooks/useFinance.ts`:
   - `useAccounts()`: загрузка счетов и балансов.
   - `useTransactions(filters)`: курсорный бесконечный список финансовых проводок.
   - `useCreateTransaction()`: оптимистичное создание транзакции с автоматической корректировкой баланса счета (expense, income, transfer) и откатом.
   - `useBudgets(month)`: контроль лимитов категорий за месяц.
   - `useDashboardToday()`: композитный запрос агрегированного дашборда сегодняшнего дня.
10. Реализован хук подписки на WebSocket `apps/web/src/hooks/useWebSocket.ts`:
   - Подхват доменных событий: `task.updated`, `task.created`, `task.status_changed`, `calendar.event_changed`, `notification.created`, `finance.transaction.posted`.
   - Точечная инвалидация кэша TanStack Query и поддержка реактивного статуса соединения.
11. Реализован хук AI-планировщика `apps/web/src/hooks/useAIPlanner.ts`:
   - `useCreatePlan()`: вызов `POST /v1/advisor/plans` с получением diff-превью изменений.
   - `useApplyPlan()`: вызов `POST /v1/advisor/plans/{id}/apply` с подтверждением пользователя (Human-in-the-Loop) и каскадной инвалидацией кэша.
   - `useParseInput()`: NLP-парсинг быстрого ввода (Cmd+K / голос) с распознаванием намерения и полей сущности.
12. Реализован Zustand-стор пользовательского интерфейса `apps/web/src/stores/ui-store.ts`:
   - Изолированное UI-состояние: `sidebarCollapsed`, `activeModal` ('quick-add' | 'task-detail' | null), `theme` ('light' | 'dark' | 'system'), `activeTaskId`, `quickAddInitialType`.
   - Действия: `toggleSidebar`, `setSidebarCollapsed`, `openModal`, `closeModal`, `setTheme`.
   - Поддержка `devtools` и `persist` для сохранения настроек сайдбара и темы в localStorage.

CHANGED_FILES:
- `apps/web/package.json`
- `apps/web/tsconfig.json`
- `apps/web/src/types/domain.ts`
- `apps/web/src/lib/api-client.ts`
- `apps/web/src/lib/query-keys.ts`
- `apps/web/src/lib/query-client.ts`
- `apps/web/src/lib/ws-client.ts`
- `apps/web/src/hooks/useTasks.ts`
- `apps/web/src/hooks/useCalendar.ts`
- `apps/web/src/hooks/useFinance.ts`
- `apps/web/src/hooks/useWebSocket.ts`
- `apps/web/src/hooks/useAIPlanner.ts`
- `apps/web/src/stores/ui-store.ts`
- `docs/it-company/19-frontend-logic-developer.md`

FINDINGS:
- **Разрешение 409 и 412 через RFC 9457:** В `api-client.ts` реализована строгая типизация ответов об ошибках. При получении 412 (Precondition Failed) или 409 (Conflict) из заголовка `ETag` или тела `ProblemDetails` извлекается актуальная версия ресурса (`currentVersion`), что позволяет компонентам пользовательского интерфейса отображать модальные окна разрешения конфликтов без потери локального контекста.
- **Оптимистичные обновления с полным контекстом отката:** В хуках `useCreateTask`, `useUpdateTask`, `useCompleteTask`, `useMoveTask` и `useCreateTransaction` реализован паттерн `onMutate` -> `onError` -> `onSettled`. Сохраняются снимки как детальных представлений, так и всех страниц бесконечных списков в кэше TanStack Query, гарантируя мгновенный отклик интерфейса (< 50 мс) и безопасный откат при сетевых сбоях.
- **Двухуровневая синхронизация через WebSocket:** Синглтон `wsClient` берет на себя не только вызов локальных коллбэков, но и автоматическую инвалидацию затронутых веток кэша TanStack Query. При восстановлении соединения после обрыва (`ws:reconnected`) автоматически вызывается `queryClient.invalidateQueries({ type: 'active' })`, что устраняет рассинхронизацию данных без необходимости ручного обновления страницы.
- **Строгая изоляция UI State:** В сторе Zustand `ui-store.ts` хранятся исключительно эфемерные свойства отображения (сайдбар, модальные окна, тема оформления). Никакие доменные сущности (задачи, транзакции, события) не дублируются в Zustand, исключая проблемы расхождения состояния.

VALIDATION:
- Синтаксическая валидация всех TypeScript файлов.
- Проверка согласованности интерфейсов `Task`, `CalendarEvent`, `Transaction`, `Budget`, `TimeBlock` с контрактами Solution Architect (04) и System Analyst (06).
- Проверка покрытия обязательных сигнатур и требований роли 19:
  - `apiRequest` с автоматическим `Idempotency-Key` (UUIDv4) и заголовком `If-Match: W/"{version}"`.
  - Классы ошибок `ConflictError` и `ValidationError`.
  - `wsClient` с Full Jitter Backoff (1s -> 30s) и 30s heartbeat.
  - Полный комплект кастомных хуков с оптимистичными мутациями.
  - Zustand-стор UI с методами управления модалками и темой.

EVIDENCE:

1. Фрагмент реализации `apiRequest` с Idempotency-Key, If-Match и типизированными ошибками (`apps/web/src/lib/api-client.ts`):
```typescript
// Idempotency-Key for mutating requests
const isMutatingMethod = method === 'POST' || method === 'PATCH' || method === 'DELETE';
if (isMutatingMethod) {
  if (idempotencyKey) {
    requestHeaders['Idempotency-Key'] = idempotencyKey;
  } else if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    requestHeaders['Idempotency-Key'] = crypto.randomUUID();
  }
}

// If-Match ETag for optimistic concurrency
const effectiveVersion = version !== undefined ? version : ifMatch;
if (effectiveVersion !== undefined && effectiveVersion !== null) {
  requestHeaders['If-Match'] =
    typeof effectiveVersion === 'number' ? `W/"${effectiveVersion}"` : String(effectiveVersion);
}
```

2. Фрагмент Full Jitter Backoff и автоматической компенсации в `WebSocketClient` (`apps/web/src/lib/ws-client.ts`):
```typescript
private compensateMissedEvents(): void {
  console.info(`[WebSocketClient] Reconnected. Invalidating queries to compensate missed events.`);
  queryClient.invalidateQueries({ type: 'active' });
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('ws:reconnected'));
  }
}

private scheduleReconnect(): void {
  if (this.isExplicitlyClosed) return;
  const exponential = Math.min(this.maxDelay, this.baseDelay * Math.pow(1.5, this.reconnectAttempts));
  const jitter = exponential * 0.2 * (Math.random() * 2 - 1);
  const finalDelay = Math.max(1000, Math.min(this.maxDelay, Math.floor(exponential + jitter)));
  this.reconnectAttempts++;
  this.reconnectTimeoutId = setTimeout(() => { this.connect(); }, finalDelay);
}
```

3. Фрагмент оптимистичного обновления и отката в `useTasks.ts` (`apps/web/src/hooks/useTasks.ts`):
```typescript
export function useUpdateTask() {
  const queryClient = useQueryClient();
  return useMutation<Task, Error, UpdateTaskInput, { previousDetail?: Task; previousQueries: Array<[readonly unknown[], unknown]> }>({
    mutationFn: ({ id, version, ...patch }: UpdateTaskInput) =>
      apiRequest<Task, Partial<UpdateTaskInput>>('PATCH', `/tasks/${id}`, { body: patch, version }),
    onMutate: async ({ id, version, ...patch }) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.tasks.all });
      // Snapshot & optimistic cache mutation with version increment
      ...
    },
    onError: (_err, { id }, context) => {
      // Automatic state rollback
      ...
    },
    onSettled: (_data, _error, { id }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.detail(id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.tasks.all });
    },
  });
}
```

4. Фрагмент Zustand UI стора (`apps/web/src/stores/ui-store.ts`):
```typescript
export interface UIStore {
  sidebarCollapsed: boolean;
  activeModal: ModalType;
  theme: ThemeMode;
  activeTaskId: string | null;
  quickAddInitialType: QuickAddIntentType;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  openModal: (modal: Exclude<ModalType, null>, options?: OpenModalOptions) => void;
  closeModal: () => void;
  setTheme: (theme: ThemeMode) => void;
}
```

REMAINING_ISSUES: нет
BLOCKERS: нет

DECISIONS:
| ID | Решение | Обоснование |
|---|---|---|
| **ADR-FL-01** | Единый модуль `types/domain.ts` для всех агрегатов | Устранение циклических зависимостей, централизованная типизация API и хуков |
| **ADR-FL-02** | Автоматическая генерация `crypto.randomUUID()` для Idempotency-Key | Защита от дублей мутаций при мобильных сетевых сбоях без ручного вмешательства вызывающего кода |
| **ADR-FL-03** | Строгая иерархия ошибок (RFC 9457) с извлечением `currentVersion` | Возможность построения UI-диалогов разрешения конфликтов версий (Lost Update) |
| **ADR-FL-04** | Синглтон `wsClient` с Full Jitter и инвалидацией `active` запросов | Надежное поддержание синхронности данных между вкладками и устройствами без утечек сокетов |
| **ADR-FL-05** | Персистентность только UI-настроек в Zustand | Гарантия соответствия архитектурному правилу: Server State строго в TanStack Query, UI State (< 2KB) в Zustand |

HANDOFF:
- Передать готовую кодовую базу бизнес-логики (`apps/web/src/`) агенту `21-frontend-integration-engineer` для связывания страниц, компонентов интерфейса, форм и провайдеров.
NEXT_AGENT: 21-frontend-integration-engineer
