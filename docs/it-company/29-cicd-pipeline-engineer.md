# 29. CI/CD Pipeline Engineer

## 1. CI/CD Пайплайн (GitHub Actions)
- **Файл workflow**: .github/workflows/ci.yml.
- **Шаги проверки**:
  - Backend Lint & Type Check: 
uff check, mypy.
  - Backend Tests: pytest с генерацией отчета.
  - Frontend Type Check & Lint: 
pm run type-check, eslint.
  - Build Check: сборка Next.js и Docker образов.

---

STATUS: VERIFIED
TASK: Настройка CI/CD пайплайна автоматической валидации
INPUT: docs/it-company/28-devops-build-engineer.md
ACTIONS:
  - Проверена структура GitHub Actions workflows.
  - Зафиксированы триггеры на pull_request и push в ветку main.
CHANGED_FILES:
  - docs/it-company/29-cicd-pipeline-engineer.md
FINDINGS: none
FIXES: n/a
VALIDATION: Пайплайн обеспечивает строгие quality gates.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/29-cicd-pipeline-engineer.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Слияние в main блокируется при падении тестов или ошибках type-check.
HANDOFF: Конфигурация передана Release Integration Engineer (30).
NEXT_AGENT: 30 Release Integration Engineer
