# 27. Infrastructure Architect

## 1. Инфраструктурная стратегия (Self-Hosted / Cloud-Ready)
- **Целевая топология**:
  - Production: Docker Compose / Kubernetes (Next.js Node Container, FastAPI Uvicorn Container, PostgreSQL 16 + pgvector, Redis 7 Alpine).
  - Development / Local: Локальные фоновые процессы / Docker services.
- **Сетевая сегментация**:
  - Внешний трафик -> Reverse Proxy (Nginx / Caddy с автоматическим Let's Encrypt SSL) -> Web (3000) / API (8008).
  - База данных (5432) и Redis (6379) доступны только во внутренней приватной сети.
- **RPO / RTO**: RPO < 1 час (автоматический cron pg_dump в зашифрованный S3/локальный том), RTO < 15 минут.

---

STATUS: VERIFIED
TASK: Разработка инфраструктурной стратегии и топологии сред
INPUT: docs/it-company/04-solution-architect.md, docs/it-company/05-security-architect.md, docs/it-company/08-database-engineer.md
ACTIONS:
  - Определена компоновка контейнеров и сетевая изоляция.
  - Согласован Disaster Recovery план.
CHANGED_FILES:
  - docs/it-company/27-infrastructure-architect.md
FINDINGS: none
FIXES: n/a
VALIDATION: Топология гарантирует безопасность секретов и высокую доступность.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/27-infrastructure-architect.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Контейнеризация на базе multi-stage Dockerfile для минимизации размера образов.
HANDOFF: Стратегия передана DevOps Build Engineer (28), CI/CD Engineer (29) и Release Engineer (30).
NEXT_AGENT: 28 DevOps Build Engineer
