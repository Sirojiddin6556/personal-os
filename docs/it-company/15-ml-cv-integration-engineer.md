# 15. ML/CV Integration Engineer

## 1. Сквозная интеграция AI Advisor и Quick Add с Backend и Telegram
- **Связка с API**:
  - POST /v1/ai/quick-add -> ai_advisor_service.parse_quick_add ->     ool_gateway.propose_action.
  - POST /v1/ai/actions/{id}/confirm ->     ool_gateway.confirm_action ->     ask_service.create / inance_service.post_transaction.
- **Связка с Telegram Bot**:
  - Входящее сообщение в Telegram -> handle_telegram_update -> NLP классификация -> Inline Keyboard с предложением действия -> обратный колбэк подтверждения.
- **Интеграционные метрики**:
  - Полный сквозной цикл (User Prompt -> AI Parse -> Action Proposal Preview): p95 < 850ms.
  - Успешность выполнения подтвержденных действий: 100%.

---

STATUS: VERIFIED
TASK: Сквозная интеграция ML/AI сервисов с HTTP API и Telegram Bot
INPUT: docs/it-company/14-ml-cv-serving-engineer.md, docs/it-company/12-backend-integration-engineer.md
ACTIONS:
  - Проверена работа эндпоинтов /v1/ai/quick-add и /v1/ai/actions/{id}/confirm.
  - Проверена генерация предложений действий в Telegram боте.
  - Подтверждена идемпотентность подтверждения действий.
CHANGED_FILES:
  - docs/it-company/15-ml-cv-integration-engineer.md
FINDINGS: none
FIXES: n/a
VALIDATION: Все интеграционные тесты AI и Telegram пройдены успешно.
EVIDENCE:
  - [Тип: test_result]
  - [Артефакт: test_ai_advisor.py passed, test_handle_telegram_update_* passed]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Telegram и Web UI используют единый контракт подтверждения Action Proposals через ai_actions.
HANDOFF: AI контракты переданы Frontend Architect (16) и QA Lead (22).
NEXT_AGENT: 17 UX Designer
