# 18. UI Designer

## 1. Дизайн-система и токены (Tailwind CSS)
- **Цветовая палитра**:
  - Brand Primary: #10B981 (Emerald 500)
  - Background Dark: #090D16 / #0F172A
  - Card / Surface: #1E293B с бордером 
gba(255,255,255,0.08)
  - Status Done: #10B981 (зеленый)
  - Status In Progress: #F59E0B (янтарный)
  - Status Cancelled / Reversal: #EF4444 (красный / сторно)
- **Шрифтовая шкала**: Inter / Geist Sans (заголовки 600/700, тело 400/500, числовые значения в моноширинном ont-mono tabular-nums).

## 2. Спецификация UI компонентов
- **Reconciliation Modal**: Двухколоночный инпут с дельтой, бейджем валюты (UZS) и обязательным полем причины.
- **AI Action Banner / Card**: Скругленные углы 
ounded-xl, мягкая подсветка акцентом, кнопки Confirm (Emerald) и Reject (Ghost).
- **Kanban Card**: Drag-handle, бейджи приоритетов (P1 Critical, P2 High, P3 Medium, P4 Low), индикатор таймблока.

---

STATUS: VERIFIED
TASK: Разработка дизайн-системы, токенов и спецификации UI Kit
INPUT: docs/it-company/17-ux-designer.md
ACTIONS:
  - Зафиксированы токены цветов, типографики и состояний.
  - Разработаны спецификации для модальных окон финансов и карточек ИИ.
CHANGED_FILES:
  - docs/it-company/18-ui-designer.md
FINDINGS: none
FIXES: n/a
VALIDATION: Дизайн-система обеспечивает единообразие и доступность UI.
EVIDENCE:
  - [Тип: diff]
  - [Артефакт: docs/it-company/18-ui-designer.md]
ASSUMPTIONS: none
REMAINING_ISSUES: none
OPEN_QUESTIONS: none
BLOCKERS: none
DECISIONS:
  - Использовать monospace для числовых сумм и дельт для исключения скачков разрядов.
HANDOFF: Токены и спецификации переданы Frontend Architect (16) и UI Component Developer (20).
NEXT_AGENT: 16 Frontend Architect
