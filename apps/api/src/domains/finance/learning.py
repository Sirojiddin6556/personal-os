"""Category learning: remember which category the user picks for a merchant or phrase.

A rule becomes automatic only after ``AUTO_AFTER`` agreeing human confirmations
(as in Family-Budget). Automatic saves never train the rule themselves, and a
different choice resets the counter, so one odd payment cannot hijack a merchant.
"""

from __future__ import annotations

from typing import List, Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.finance.bank_notices import merchant_key
from src.domains.finance.category_match import best_match, candidates
from src.domains.finance.models import Category, CategoryRule

AUTO_AFTER = 1  # every save is automatic; one correction re-trains the merchant


def is_auto(rule: Optional[CategoryRule]) -> bool:
    return bool(rule and not rule.auto_disabled and rule.confirmations >= AUTO_AFTER)


async def get_rule(session: AsyncSession, workspace_id: UUID, key: str, kind: str) -> Optional[CategoryRule]:
    if not key:
        return None
    res = await session.execute(
        select(CategoryRule).where(
            CategoryRule.workspace_id == workspace_id,
            CategoryRule.key == key,
            CategoryRule.kind == kind,
        )
    )
    return res.scalar_one_or_none()


async def learn(session: AsyncSession, workspace_id: UUID, key: str, kind: str, category_id: UUID) -> CategoryRule:
    """Record one human confirmation. Caller commits."""
    rule = await get_rule(session, workspace_id, key, kind)
    if rule is None:
        rule = CategoryRule(workspace_id=workspace_id, key=key, kind=kind, category_id=category_id, confirmations=1)
        session.add(rule)
    elif rule.category_id == category_id:
        rule.confirmations += 1
    else:
        rule.category_id = category_id
        rule.confirmations = 1
        rule.auto_disabled = False
    await session.flush()
    return rule


async def categories_of(session: AsyncSession, workspace_id: UUID, kind: str) -> List[Category]:
    res = await session.execute(
        select(Category)
        .where(Category.workspace_id == workspace_id, Category.type == kind)
        .order_by(Category.name.asc())
    )
    return list(res.scalars().all())


async def resolve_category(
    session: AsyncSession, workspace_id: UUID, text: str, kind: str = "expense"
) -> Optional[Category]:
    """Learned rule first, then a clear fuzzy match against the workspace's categories."""
    cats = await categories_of(session, workspace_id, kind)
    if not cats:
        return None
    rule = await get_rule(session, workspace_id, merchant_key(text), kind)
    if rule is not None:
        found = next((c for c in cats if c.id == rule.category_id), None)
        if found is not None:
            return found
    return best_match(text, cats, name_of=lambda c: c.name)


def ranked_options(cats: Sequence[Category], text: str, preferred: Optional[UUID], limit: int = 8) -> List[Category]:
    """Learned category first, then fuzzy candidates, then the rest alphabetically."""
    ordered: List[Category] = []
    if preferred is not None:
        ordered += [c for c in cats if c.id == preferred]
    if text:
        ordered += [c for c in candidates(text, cats, name_of=lambda c: c.name) if c not in ordered]
    ordered += [c for c in cats if c not in ordered]
    return ordered[:limit]
