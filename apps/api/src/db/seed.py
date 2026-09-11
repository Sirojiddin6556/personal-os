"""Database seed script for Personal OS.
Populates realistic sample data across Projects, Tasks, Calendar, Finance, and Planner domains.
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_session_factory, set_tenant_context
from src.domains.identity.models import Membership, User, Workspace
from src.domains.identity.service import hash_password
from src.domains.projects.models import Project
from src.domains.tasks.models import Task
from src.domains.calendar.models import Event
from src.domains.finance.models import Account, Category, Transaction, Budget
from src.domains.planner.models import DailyJournal, Habit, HabitLog, PlannerReminder


async def seed_data():
    print("🚀 Starting Personal OS Database Seeding...")

    async with async_session_factory() as session:
        # 1. User & Workspace
        stmt_user = select(User).where(User.email == "siroj@personal-os.local")
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            user = User(
                email="siroj@personal-os.local",
                password_hash=hash_password("password123"),
                full_name="Siroj",
                status="active",
                is_active=True,
                timezone="UTC",
                locale="ru",
            )
            session.add(user)
            await session.flush()
            print("✓ Created default user: Siroj")

        stmt_ws = (
            select(Workspace)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(Membership.user_id == user.id)
        )
        res_ws = await session.execute(stmt_ws)
        workspace = res_ws.scalar_one_or_none()

        if not workspace:
            workspace = Workspace(
                name="Personal OS",
                slug="personal-os",
                owner_id=user.id,
                plan="pro",
                plan_tier="pro",
                settings={},
            )
            session.add(workspace)
            await session.flush()

            membership = Membership(
                user_id=user.id,
                workspace_id=workspace.id,
                role="owner",
                status="active",
            )
            session.add(membership)
            await session.flush()
            print("✓ Created workspace: Personal OS")

        # Set RLS Tenant Context
        await set_tenant_context(session, workspace.id)

        # 2. Projects
        res_projects = await session.execute(
            select(Project).where(Project.workspace_id == workspace.id)
        )
        existing_projects = {p.name: p for p in res_projects.scalars().all()}

        project_defs = [
            {
                "name": "Frontend Redesign",
                "description": "Модернизация интерфейса, UI/UX и адаптивность Next.js",
                "color": "#0ea5e9",
                "icon": "layout",
                "github_repo": "siroj/personal-os",
            },
            {
                "name": "Backend Core API",
                "description": "FastAPI микросервисы, PostgreSQL RLS, WebSockets и Celery",
                "color": "#6366f1",
                "icon": "server",
                "github_repo": "siroj/personal-os",
            },
            {
                "name": "Личные цели",
                "description": "Здоровье, спорт, непрерывное обучение и привычки",
                "color": "#10b981",
                "icon": "user",
                "github_repo": None,
            },
            {
                "name": "Инфраструктура & DevOps",
                "description": "Docker, CI/CD GitHub Actions, Nginx и мониторинг",
                "color": "#ef4444",
                "icon": "cpu",
                "github_repo": "siroj/infra",
            },
        ]

        created_projects = {}
        for p_def in project_defs:
            if p_def["name"] not in existing_projects:
                proj = Project(
                    workspace_id=workspace.id,
                    name=p_def["name"],
                    description=p_def["description"],
                    color=p_def["color"],
                    icon=p_def["icon"],
                    github_repo=p_def["github_repo"],
                    status="active",
                )
                session.add(proj)
                await session.flush()
                created_projects[p_def["name"]] = proj
                print(f"✓ Added project: {p_def['name']}")
            else:
                created_projects[p_def["name"]] = existing_projects[p_def["name"]]

        # 3. Tasks
        res_tasks = await session.execute(
            select(Task).where(Task.workspace_id == workspace.id)
        )
        existing_tasks = {t.title: t for t in res_tasks.scalars().all()}

        now = datetime.now(timezone.utc)
        today = date.today()

        task_defs = [
            {
                "title": "Завершить интеграцию с GitHub",
                "description": "Подключение токена, импорт репозиториев, коммиты и задачи",
                "status": "done",
                "priority": "critical",
                "project": "Backend Core API",
                "estimate": 120,
                "due_at": now - timedelta(hours=4),
                "completed_at": now - timedelta(hours=2),
            },
            {
                "title": "Реализовать фильтрацию задач по проектам",
                "description": "Синхронизация query params в адресной строке и отображение бейджей",
                "status": "done",
                "priority": "high",
                "project": "Frontend Redesign",
                "estimate": 60,
                "due_at": now - timedelta(hours=2),
                "completed_at": now - timedelta(hours=1),
            },
            {
                "title": "Подготовить релизную документацию Personal OS",
                "description": "Описать архитектуру, запуск сервисов и API эндпоинты",
                "status": "in_progress",
                "priority": "medium",
                "project": "Frontend Redesign",
                "estimate": 90,
                "due_at": now + timedelta(days=1),
                "completed_at": None,
            },
            {
                "title": "Синхронизация Google Calendar с тайм-блоками",
                "description": "Двусторонняя синхронизация встреч и слотов концентрации",
                "status": "todo",
                "priority": "high",
                "project": "Backend Core API",
                "estimate": 180,
                "due_at": now + timedelta(days=2),
                "completed_at": None,
            },
            {
                "title": "Настроить мониторинг и алерты Prometheus",
                "description": "Метрики производительности, latency и ошибки в Grafana",
                "status": "todo",
                "priority": "medium",
                "project": "Инфраструктура & DevOps",
                "estimate": 150,
                "due_at": now + timedelta(days=3),
                "completed_at": None,
            },
            {
                "title": "Пробежка 5 км в парке",
                "description": "Поддержание кардио-выносливости перед работой",
                "status": "todo",
                "priority": "low",
                "project": "Личные цели",
                "estimate": 45,
                "due_at": now + timedelta(hours=8),
                "completed_at": None,
            },
            {
                "title": "Заказать новые книги по системному дизайну",
                "description": "Designing Data-Intensive Applications & Clean Architecture",
                "status": "inbox",
                "priority": "low",
                "project": "Личные цели",
                "estimate": 20,
                "due_at": None,
                "completed_at": None,
            },
            {
                "title": "Оптимизация HNSW индексов и векторного поиска",
                "description": "Ускорение семантического поиска по заметкам и базе знаний",
                "status": "inbox",
                "priority": "high",
                "project": "Backend Core API",
                "estimate": 80,
                "due_at": None,
                "completed_at": None,
            },
        ]

        for t_def in task_defs:
            if t_def["title"] not in existing_tasks:
                proj = created_projects.get(t_def["project"])
                task = Task(
                    workspace_id=workspace.id,
                    title=t_def["title"],
                    description=t_def["description"],
                    status=t_def["status"],
                    priority=t_def["priority"],
                    project_id=proj.id if proj else None,
                    estimate_minutes=t_def["estimate"],
                    due_at=t_def["due_at"],
                    completed_at=t_def["completed_at"],
                )
                session.add(task)
                print(f"✓ Added task: {t_def['title']}")

        # 4. Calendar Events
        res_events = await session.execute(
            select(Event).where(Event.workspace_id == workspace.id)
        )
        existing_events = {e.title: e for e in res_events.scalars().all()}

        today_start = datetime(today.year, today.month, today.day, 9, 0, tzinfo=timezone.utc)
        events_defs = [
            {
                "title": "Daily Standup & Планирование спринта",
                "description": "Синхронизация задач и приоритетов на день",
                "starts_at": today_start,
                "ends_at": today_start + timedelta(minutes=30),
                "location": "Google Meet",
            },
            {
                "title": "Архитектурный синк по API Personal OS",
                "description": "Обсуждение схемы данных и интеграций с сервисами",
                "starts_at": today_start + timedelta(hours=5),
                "ends_at": today_start + timedelta(hours=6),
                "location": "Конференц-зал / Онлайн",
            },
            {
                "title": "Ревью пулреквестов и деплой на стейджинг",
                "description": "Проверка кода, E2E тесты и релизная сборка",
                "starts_at": today_start + timedelta(hours=8),
                "ends_at": today_start + timedelta(hours=9),
                "location": "GitHub Actions",
            },
        ]

        for e_def in events_defs:
            if e_def["title"] not in existing_events:
                ev = Event(
                    workspace_id=workspace.id,
                    title=e_def["title"],
                    description=e_def["description"],
                    starts_at=e_def["starts_at"],
                    ends_at=e_def["ends_at"],
                    location=e_def["location"],
                    is_all_day=False,
                    status="confirmed",
                    sync_status="local",
                )
                session.add(ev)
                print(f"✓ Added calendar event: {e_def['title']}")

        # 5. Finance Accounts, Categories, Budgets, and Transactions (Uzbekistan Segment)
        # Clean existing financial records to ensure complete localization
        await session.execute(
            text("TRUNCATE TABLE transactions, budget_periods, budgets, categories, accounts CASCADE")
        )
        await session.flush()

        account_defs = [
            {
                "name": "Uzcard (Капиталбанк)",
                "type": "checking",
                "balance_minor": 1250000000, # 12,500,000 сум
                "currency": "UZS",
            },
            {
                "name": "Humo (Anorbank)",
                "type": "checking",
                "balance_minor": 840000000, # 8,400,000 сум
                "currency": "UZS",
            },
            {
                "name": "Накопительный (Uzum Bank)",
                "type": "savings",
                "balance_minor": 3500000000, # 35,000,000 сум
                "currency": "UZS",
            },
            {
                "name": "Наличные в кошельке (UZS)",
                "type": "cash",
                "balance_minor": 150000000, # 1,500,000 сум
                "currency": "UZS",
            },
            {
                "name": "Валютная карта USD (Visa)",
                "type": "savings",
                "balance_minor": 250000, # $2,500
                "currency": "USD",
            },
        ]

        created_accs = {}
        for a_def in account_defs:
            acc = Account(
                workspace_id=workspace.id,
                name=a_def["name"],
                account_type=a_def["type"],
                balance_minor=a_def["balance_minor"],
                initial_balance_minor=a_def["balance_minor"],
                currency=a_def["currency"],
            )
            session.add(acc)
            await session.flush()
            created_accs[a_def["name"]] = acc
            print(f"✓ Added financial account: {a_def['name']}")

        # 6. Finance Categories & Transactions
        cat_defs = [
            {"name": "Продукты и Korzinka / Makro", "type": "expense", "color": "#f59e0b", "icon": "shopping-cart"},
            {"name": "Кафе, рестораны и Чайхана", "type": "expense", "color": "#ea580c", "icon": "coffee"},
            {"name": "Транспорт и Yandex Go", "type": "expense", "color": "#0ea5e9", "icon": "car"},
            {"name": "Связь, интернет и коммуналка", "type": "expense", "color": "#818cf8", "icon": "smartphone"},
            {"name": "Одежда и Uzum Market", "type": "expense", "color": "#7c3aed", "icon": "shopping-bag"},
            {"name": "Здоровье и аптека", "type": "expense", "color": "#10b981", "icon": "activity"},
            {"name": "Доход от разработки и IT", "type": "income", "color": "#22c55e", "icon": "trending-up"},
        ]

        created_cats = {}
        for c_def in cat_defs:
            cat = Category(
                workspace_id=workspace.id,
                name=c_def["name"],
                type=c_def["type"],
                color=c_def["color"],
                icon=c_def["icon"],
            )
            session.add(cat)
            await session.flush()
            created_cats[c_def["name"]] = cat
            print(f"✓ Added category: {c_def['name']}")

        # Seed Budgets
        budget_defs = [
            {"name": "Продукты и Korzinka / Makro", "cat": "Продукты и Korzinka / Makro", "amount": 450000000},
            {"name": "Кафе, рестораны и Чайхана", "cat": "Кафе, рестораны и Чайхана", "amount": 250000000},
            {"name": "Транспорт и Yandex Go", "cat": "Транспорт и Yandex Go", "amount": 120000000},
            {"name": "Связь, интернет и коммуналка", "cat": "Связь, интернет и коммуналка", "amount": 80000000},
        ]
        for b_def in budget_defs:
            c_obj = created_cats.get(b_def["cat"])
            b = Budget(
                workspace_id=workspace.id,
                category_id=c_obj.id if c_obj else None,
                name=b_def["name"],
                amount_minor=b_def["amount"],
                currency="UZS",
                period_type="monthly",
            )
            session.add(b)

        # Seed Transactions in UZS
        uzcard_acc = created_accs.get("Uzcard (Капиталбанк)")
        humo_acc = created_accs.get("Humo (Anorbank)")
        uzum_acc = created_accs.get("Накопительный (Uzum Bank)")

        tx_samples = [
            {
                "account": uzcard_acc,
                "amount_minor": 45000000, # 450,000 сум
                "type": "expense",
                "description": "Покупки в супермаркете Korzinka.uz",
                "category": "Продукты и Korzinka / Makro",
                "occurred_at": now - timedelta(hours=3),
            },
            {
                "account": humo_acc,
                "amount_minor": 12000000, # 120,000 сум
                "type": "expense",
                "description": "Обед в Milliy Taomlar (плов, салат, чай)",
                "category": "Кафе, рестораны и Чайхана",
                "occurred_at": now - timedelta(hours=6),
            },
            {
                "account": uzcard_acc,
                "amount_minor": 3500000, # 35,000 сум
                "type": "expense",
                "description": "Поездка в Yandex Go Комфорт",
                "category": "Транспорт и Yandex Go",
                "occurred_at": now - timedelta(days=1, hours=2),
            },
            {
                "account": uzcard_acc,
                "amount_minor": 18000000, # 180,000 сум
                "type": "expense",
                "description": "Оплата оптоволоконного интернета и мобильного через Payme",
                "category": "Связь, интернет и коммуналка",
                "occurred_at": now - timedelta(days=1, hours=8),
            },
            {
                "account": uzum_acc,
                "amount_minor": 29000000, # 290,000 сум
                "type": "expense",
                "description": "Заказ товаров для дома на Uzum Market",
                "category": "Одежда и Uzum Market",
                "occurred_at": now - timedelta(days=2),
            },
            {
                "account": humo_acc,
                "amount_minor": 8500000, # 85,000 сум
                "type": "expense",
                "description": "Покупка витаминов в аптеке OxyMed",
                "category": "Здоровье и аптека",
                "occurred_at": now - timedelta(days=3),
            },
            {
                "account": uzcard_acc,
                "amount_minor": 2800000000, # 28,000,000 сум
                "type": "income",
                "description": "Поступление гонорара за разработку Personal OS",
                "category": "Доход от разработки и IT",
                "occurred_at": now - timedelta(days=4),
            },
        ]

        for tx_data in tx_samples:
            cat_obj = created_cats.get(tx_data["category"])
            target_acc = tx_data["account"] or uzcard_acc
            if target_acc:
                tx = Transaction(
                    workspace_id=workspace.id,
                    account_id=target_acc.id,
                    amount_minor=tx_data["amount_minor"],
                    currency="UZS",
                    transaction_type=tx_data["type"],
                    status="posted",
                    category_id=cat_obj.id if cat_obj else None,
                    occurred_at=tx_data["occurred_at"],
                    posted_at=tx_data["occurred_at"],
                    note=tx_data["description"],
                )
                session.add(tx)
        print("✓ Added localized Uzbekistan transactions to financial ledger")

        # 7. Planner Habits
        res_habits = await session.execute(
            select(Habit).where(Habit.workspace_id == workspace.id)
        )
        existing_habits = {h.title: h for h in res_habits.scalars().all()}

        habit_defs = [
            {"title": "Утренняя зарядка и разминка", "target": 1, "streak": 12, "best": 25},
            {"title": "Чтение технической литературы (30 мин)", "target": 1, "streak": 8, "best": 15},
            {"title": "Код-ревью и коммиты в репозиторий", "target": 1, "streak": 19, "best": 30},
            {"title": "Выпить 2.5л воды за день", "target": 1, "streak": 5, "best": 14},
        ]

        for h_def in habit_defs:
            if h_def["title"] not in existing_habits:
                h = Habit(
                    workspace_id=workspace.id,
                    title=h_def["title"],
                    frequency_type="daily",
                    target_count=h_def["target"],
                    current_streak=h_def["streak"],
                    best_streak=h_def["best"],
                    is_archived=False,
                )
                session.add(h)
                await session.flush()
                # Add log for today
                h_log = HabitLog(
                    workspace_id=workspace.id,
                    habit_id=h.id,
                    logged_date=today,
                    count=1,
                    notes="Выполнено",
                )
                session.add(h_log)
                print(f"✓ Added habit: {h_def['title']}")

        # 8. Daily Journal for Today
        res_dj = await session.execute(
            select(DailyJournal).where(
                DailyJournal.workspace_id == workspace.id,
                DailyJournal.entry_date == today,
            )
        )
        if not res_dj.scalar_one_or_none():
            dj = DailyJournal(
                workspace_id=workspace.id,
                entry_date=today,
                morning_intention="Сфокусироваться на полировке Personal OS и идеальной консистентности всех модулей.",
                gratitude="Продуктивная работа, новые инсайты по архитектуре и быстрое решение задач.",
                notes="Все модули работают синхронно, UI откликается мгновенно.",
                evening_reflection="Отличный день, все ключевые задачи завершены вовремя.",
                mood="focused",
                productivity_rating=5,
            )
            session.add(dj)
            print("✓ Added Daily Journal reflection for today")

        # 9. Planner Reminders
        res_rem = await session.execute(
            select(PlannerReminder).where(PlannerReminder.workspace_id == workspace.id)
        )
        if len(res_rem.scalars().all()) == 0:
            reminders = [
                {
                    "title": "Выпить стакан воды и сделать перерыв для глаз",
                    "remind_at": now + timedelta(minutes=45),
                    "remind_type": "water",
                },
                {
                    "title": "Проверить статус сборки и открытые тикеты",
                    "remind_at": now + timedelta(hours=2),
                    "remind_type": "task",
                },
            ]
            for r in reminders:
                prem = PlannerReminder(
                    workspace_id=workspace.id,
                    title=r["title"],
                    remind_at=r["remind_at"],
                    remind_type=r["remind_type"],
                    is_dismissed=False,
                )
                session.add(prem)
            print("✓ Added planner reminders")

        await session.commit()
        print("🎉 Database seeding finished successfully!")


if __name__ == "__main__":
    asyncio.run(seed_data())
