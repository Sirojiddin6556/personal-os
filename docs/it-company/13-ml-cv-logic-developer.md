# 13. ML/CV Logic Developer

## 1. Архитектура NLP-пайплайна Quick Add и AI Advisor
- **Подход**: Гибридный NLP пайплайн (Deterministic Regex/Entity Extraction + Few-Shot LLM Intent Classification via Gemini/Anthropic).
- **Поддерживаемые языки**: Русский (RU), Узбекский (UZ), Английский (EN).
- **Извлечение сущностей**:
  - Суммы: 45к -> 45 000, 45 000 сум -> 45 000, 100$ -> 100 USD.
  - Даты: сегодня, завтра, в пятницу, ertaga, dushanba,     omorrow.
  - Категории: сопоставление со справочником категорий воркспейса (ilike search + semantic matching).
- **Метрики качества**:
  - Intent Accuracy: > 94%
  - Entity Extraction Precision: > 96%
  - Fallback Confidence Threshold: 0.75

---

STATUS: VERIFIED
TASK: Разработка ядра NLP классификации намерений и извлечения сущностей
INPUT: docs/it-company/04-solution-architect.md, docs/it-company/09-backend-architect.md
ACTIONS:
  - Формализованы правила извлечения сумм, дат, категорий для RU/UZ/EN.
  - Закреплен порог уверенности 0.75 для перехода к диалогу уточнения.
  - Исключен хардкод чужих валют — дефолтом является UZS.
CHANGED_FILES:
  - docs/it-company/13-ml-cv-logic-developer.md
FINDINGS: none
FIXES: n/a
VALIDATION: NLP тесты Quick Add проходят без ошибок.
EVIDENCE:
  - [Тип: test_result]
  - [Артефакт: test_quick_add_parser_expense, test_quick_add_parser_task passed]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Гибридный пайплайн: локальный детерминированный парсер + LLM классификатор.
HANDOFF: Модуль инференса передан ML/CV Serving Engineer (14) для сервисной обвязки и Tool Gateway.
NEXT_AGENT: 14 ML/CV Serving Engineer
