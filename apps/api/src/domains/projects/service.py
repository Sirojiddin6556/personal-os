"""Projects, Goals and Milestones domain service."""

from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.projects.models import Goal, Milestone, Project
from src.domains.projects.schemas import (
    GoalCreate,
    GoalUpdate,
    MilestoneCreate,
    MilestoneUpdate,
    ProjectCreate,
    ProjectUpdate,
)
from src.shared.exceptions import NotFoundError
from src.shared.outbox import publish_event


class ProjectService:
    """Business operations for Goals, Projects and Milestones."""

    # --- Goals ---
    async def create_goal(self, session: AsyncSession, workspace_id: UUID, body: GoalCreate) -> Goal:
        goal = Goal(
            id=uuid4(),
            workspace_id=workspace_id,
            title=body.title,
            description=body.description,
            category=body.category,
            target_date=body.target_date,
            status=body.status,
            progress_percentage=body.progress_percentage,
        )
        session.add(goal)
        await publish_event(
            session=session,
            event_type="goal.created.v1",
            aggregate_type="goal",
            aggregate_id=goal.id,
            workspace_id=workspace_id,
            data={"title": goal.title},
        )
        await session.commit()
        await session.refresh(goal)
        return goal

    async def list_goals(self, session: AsyncSession, workspace_id: UUID) -> List[Goal]:
        stmt = select(Goal).where(Goal.workspace_id == workspace_id).order_by(Goal.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_goal(self, session: AsyncSession, workspace_id: UUID, goal_id: UUID) -> Goal:
        stmt = select(Goal).where(Goal.id == goal_id, Goal.workspace_id == workspace_id)
        res = await session.execute(stmt)
        goal = res.scalar_one_or_none()
        if not goal:
            raise NotFoundError(resource="Goal", identifier=goal_id)
        return goal

    async def update_goal(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        goal_id: UUID,
        body: GoalUpdate,
    ) -> Goal:
        goal = await self.get_goal(session, workspace_id, goal_id)
        data = body.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(goal, k, v)
        await publish_event(
            session=session,
            event_type="goal.updated.v1",
            aggregate_type="goal",
            aggregate_id=goal.id,
            workspace_id=workspace_id,
            data={"title": goal.title, "status": goal.status},
        )
        await session.commit()
        await session.refresh(goal)
        return goal

    async def delete_goal(self, session: AsyncSession, workspace_id: UUID, goal_id: UUID) -> None:
        goal = await self.get_goal(session, workspace_id, goal_id)
        await session.delete(goal)
        await publish_event(
            session=session,
            event_type="goal.deleted.v1",
            aggregate_type="goal",
            aggregate_id=goal_id,
            workspace_id=workspace_id,
            data={"title": goal.title},
        )
        await session.commit()

    # --- Projects ---
    async def create_project(self, session: AsyncSession, workspace_id: UUID, body: ProjectCreate) -> Project:
        project = Project(
            id=uuid4(),
            workspace_id=workspace_id,
            goal_id=body.goal_id,
            name=body.name,
            description=body.description,
            color=body.color,
            icon=body.icon,
            status=body.status,
            target_date=body.target_date,
            github_repo=body.github_repo,
            github_default_branch=body.github_default_branch or "main",
        )
        session.add(project)
        await publish_event(
            session=session,
            event_type="project.created.v1",
            aggregate_type="project",
            aggregate_id=project.id,
            workspace_id=workspace_id,
            data={"name": project.name, "status": project.status, "github_repo": project.github_repo},
        )
        await session.commit()
        await session.refresh(project)
        return project

    async def list_projects(self, session: AsyncSession, workspace_id: UUID) -> List[Project]:
        stmt = select(Project).where(Project.workspace_id == workspace_id).order_by(Project.created_at.desc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_project(self, session: AsyncSession, workspace_id: UUID, project_id: UUID) -> Project:
        stmt = select(Project).where(Project.id == project_id, Project.workspace_id == workspace_id)
        res = await session.execute(stmt)
        proj = res.scalar_one_or_none()
        if not proj:
            raise NotFoundError(resource="Project", identifier=project_id)
        return proj

    async def update_project(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        project_id: UUID,
        body: ProjectUpdate,
    ) -> Project:
        proj = await self.get_project(session, workspace_id, project_id)
        data = body.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(proj, k, v)
        await publish_event(
            session=session,
            event_type="project.updated.v1",
            aggregate_type="project",
            aggregate_id=proj.id,
            workspace_id=workspace_id,
            data={"name": proj.name, "status": proj.status},
        )
        await session.commit()
        await session.refresh(proj)
        return proj

    async def delete_project(self, session: AsyncSession, workspace_id: UUID, project_id: UUID) -> None:
        proj = await self.get_project(session, workspace_id, project_id)
        await session.delete(proj)
        await publish_event(
            session=session,
            event_type="project.deleted.v1",
            aggregate_type="project",
            aggregate_id=project_id,
            workspace_id=workspace_id,
            data={"name": proj.name},
        )
        await session.commit()

    # --- Milestones ---
    async def create_milestone(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        body: MilestoneCreate,
    ) -> Milestone:
        milestone = Milestone(
            id=uuid4(),
            workspace_id=workspace_id,
            goal_id=body.goal_id,
            project_id=body.project_id,
            title=body.title,
            due_date=body.due_date,
            status=body.status,
        )
        session.add(milestone)
        await publish_event(
            session=session,
            event_type="milestone.created.v1",
            aggregate_type="milestone",
            aggregate_id=milestone.id,
            workspace_id=workspace_id,
            data={"title": milestone.title, "due_date": milestone.due_date.isoformat()},
        )
        await session.commit()
        await session.refresh(milestone)
        return milestone

    async def list_milestones(self, session: AsyncSession, workspace_id: UUID) -> List[Milestone]:
        stmt = select(Milestone).where(Milestone.workspace_id == workspace_id).order_by(Milestone.due_date.asc())
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_milestone(self, session: AsyncSession, workspace_id: UUID, milestone_id: UUID) -> Milestone:
        stmt = select(Milestone).where(Milestone.id == milestone_id, Milestone.workspace_id == workspace_id)
        res = await session.execute(stmt)
        m = res.scalar_one_or_none()
        if not m:
            raise NotFoundError(resource="Milestone", identifier=milestone_id)
        return m

    async def update_milestone(
        self,
        session: AsyncSession,
        workspace_id: UUID,
        milestone_id: UUID,
        body: MilestoneUpdate,
    ) -> Milestone:
        m = await self.get_milestone(session, workspace_id, milestone_id)
        data = body.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(m, k, v)
        await publish_event(
            session=session,
            event_type="milestone.updated.v1",
            aggregate_type="milestone",
            aggregate_id=m.id,
            workspace_id=workspace_id,
            data={"title": m.title, "status": m.status},
        )
        await session.commit()
        await session.refresh(m)
        return m

    async def delete_milestone(self, session: AsyncSession, workspace_id: UUID, milestone_id: UUID) -> None:
        m = await self.get_milestone(session, workspace_id, milestone_id)
        await session.delete(m)
        await publish_event(
            session=session,
            event_type="milestone.deleted.v1",
            aggregate_type="milestone",
            aggregate_id=milestone_id,
            workspace_id=workspace_id,
            data={"title": m.title},
        )
        await session.commit()


project_service = ProjectService()

