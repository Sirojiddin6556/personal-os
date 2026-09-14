# 05. Security Architect (Архитектор безопасности)

## 1. Модель угроз (STRIDE)

| Угроза (STRIDE) | Вектор атаки | Архитектурная защита |
|---|---|---|
| **Spoofing** (Подмена пользователя) | Подделка JWT токена или подмена Telegram User ID | Подпись JWT (HS256/RS256) с валидацией exp/iss; deep-link привязка Telegram chat к воркспейсу; проверка вебхук-секрета через hmac.compare_digest. |
| **Tampering** (Искажение данных) | Ручная подмена баланса счёта или параметров транзакции | Неизменяемый журнал транзакций (Ledger); блокировка прямого PATCH баланса; вычисление остатка по транзакциям. |
| **Repudiation** (Отказ от авторства) | Несанкционированные действия AI или сторнирование | Полный аудит-лог (audit_logs, ai_actions) с фиксацией user_id, reversal_reason, idempotency_key,     imestamp. |
| **Information Disclosure** (Утечка данных) | Cross-tenant утечка данных между воркспейсами; утечка API ключей | PostgreSQL Row Level Security (RLS) с принудительным SET LOCAL app.current_workspace_id; шифрование секретов AES-256-GCM в БД. |
| **Denial of Service** (Отказ в обслуживании) | Флуд вебхуков Telegram / повтор OAuth запросов | Fast ACK (<500ms) с асинхронной обработкой в BackgroundTasks; Redis дедупликация (SETNX). |
| **Elevation of Privilege** (Эскалация привилегий) | Несанкционированное выполнение ИИ опасных мутаций/удалений | Строгий Tool Gateway с 6 уровнями рисков: Tier 3-5 требуют обязательного Preview и подтверждения пользователем; Tier 6 заблокирован. |

---

## 2. Спецификация требований безопасности (Security Requirements)
- **SEC-01 (Изоляция данных)**: Все таблицы, содержащие workspace_id, должны иметь включенный RLS (ENABLE ROW LEVEL SECURITY, FORCE ROW LEVEL SECURITY).
- **SEC-02 (Шифрование секретов)**: Токены интеграций (Telegram bot token, Google OAuth client secret, GitHub PAT) шифруются алгоритмом AES-256-GCM.
- **SEC-03 (Защита финансовых инвариантов)**: Поле balance_minor счёта запрещено к прямой модификации через API. Изменения баланса происходят только через добавление транзакции.
- **SEC-04 (Безопасность ИИ-агентов)**: Предложения действий (Action Proposals) хранятся в БД с TTL = 15 минут, хэшем сущности и проверкой ключа идемпотентности.

---

STATUS: VERIFIED
TASK: Разработка модели угроз STRIDE и требований безопасности
INPUT: docs/it-company/04-solution-architect.md, PRD, BRD
ACTIONS:
  - Проведен STRIDE-анализ компонентов и точек интеграции.
  - Сформирован реестр требований безопасности SEC-01 - SEC-04.
  - Зафиксированы правила защиты RLS, AES-256-GCM и Tool Gateway.
CHANGED_FILES:
  - docs/it-company/05-security-architect.md
FINDINGS: none
FIXES: n/a
VALIDATION: Модель угроз полностью покрывает мультиарендность, финансы и ИИ-инструменты.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/05-security-architect.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Обязательный RLS на всех таблицах воркспейса.
  - AES-256-GCM для всех пользовательских интеграционных ключей.
  - Tool Gateway блокирует прямое выполнение Tier 3-6 действий.
HANDOFF: Требования безопасности переданы System Analyst (06), Database Architect (07) и Backend Architect (09).
NEXT_AGENT: 06 System Analyst
