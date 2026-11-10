"""Fully automatic categorization of bank operations and text expenses.

Order: the user's own learned rule (any correction they made) -> built-in
dictionary of Uzbek merchants/keywords (extends Family-Budget's RULES) -> a
clear fuzzy match against the workspace's categories -> a fallback category.
Missing categories are created on first use, so nothing ever waits for input.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.domains.finance import learning
from src.domains.finance.bank_notices import learnable_merchant, merchant_key
from src.domains.finance.category_match import best_match
from src.domains.finance.models import Category

# (regex on normalized merchant/description, kind, category name, color)
RULES: List[Tuple[str, str, str, str]] = [
    # transfers / cash first: they must never be taken for a shop
    (r"\bp2p\b|perevod|перевод|transfer|\bh2u\b|\bu2h\b|\bh2h\b|\bu2u\b|card ?to ?card|kartadan|o.?tkazma", "expense", "Переводы", "#64748B"),
    (r"\batm\b|bankomat|банкомат|наличн|cash ?out|снятие|naqd", "expense", "Наличные", "#78716C"),
    (r"komissiya|комисси|commission|\bfee\b|sms.?(?:xabar|info|инфо)|обслуживани|xizmat haqi", "expense", "Банк и комиссии", "#94A3B8"),
    (r"kredit|кредит|loan|погашени|ipoteka to.?lov|muddatli", "expense", "Кредиты", "#B91C1C"),
    # food
    (r"wolt|express ?24|tezkor|yandex ?(?:eda|eats)|delivery|доставк", "expense", "Доставка еды", "#F97316"),
    (r"evos|kfc|les ?ailes|oqtepa|max ?way|feed ?up|bellissimo|chopar|safia|starbucks|wendy|burger|pizza|пицц|"
     r"cafe|kafe|кафе|coffee|кофе|restoran|ресторан|restaurant|choyxona|lavash|osh ?markaz|kebab|sushi|суши|bistro|fast ?food",
     "expense", "Кафе и рестораны", "#EF4444"),
    (r"uzum ?market|wildberries|ozon|aliexpress|olcha|asaxiy|texnomart|mediapark|idea|elmakon|artel|samsung|apple ?store",
     "expense", "Покупки и техника", "#8B5CF6"),
    (r"korzinka|makro|havas|baraka|carrefour|magnum|\bbi1\b|anglesey|supermarket|супермаркет|market|маркет|oziq|"
     r"продукт|bozor|базар|food ?city|mega ?planet|g.?alla|non ?uyi|go.?sht|meat|мяс|молок|хлеб|овощ|фрукт",
     "expense", "Продукты", "#10B981"),
    # transport
    (r"yandex ?(?:go|taxi)|yango|my ?taxi|uklon|millennium|taxi|такси|taksi", "expense", "Такси", "#EAB308"),
    (r"\bazs\b|азс|neftegaz|lukoil|mustang|saxovat|benzin|бензин|propan|metan|метан|заправ|gas ?station|fuel",
     "expense", "Топливо", "#CA8A04"),
    (r"metro|метро|\batto\b|avtobus|автобус|\bbus\b|temir ?yo|railway|poezd|поезд|airways|avia|авиа|parking|парковк",
     "expense", "Транспорт", "#F59E0B"),
    # bills
    (r"beeline|ucell|uzmobile|mobiuz|uztelecom|perfectum|turon ?tel|sarkor|comnet|\bevo\b|internet|интернет|mobil",
     "expense", "Связь и интернет", "#0EA5E9"),
    (r"hududgaz|худудгаз|elektr|электр|energosotish|issiqlik|suvsoz|suv ?ta|toza ?hudud|kommunal|коммунал|uy ?joy",
     "expense", "Коммунальные услуги", "#06B6D4"),
    # health, shopping, fun
    (r"apteka|аптек|pharm|dori|klinika|clinic|клиник|stomat|стомат|hospital|med ?center|tibbiy|laborator",
     "expense", "Здоровье", "#22C55E"),
    (r"zara|lc ?waikiki|defacto|koton|mango|h&m|adidas|nike|puma|colin|одежд|kiyim|poyabzal|обув",
     "expense", "Одежда и обувь", "#EC4899"),
    (r"cinema|kino|кино|magic ?city|netflix|spotify|youtube|steam|playstation|google ?play|apple\.com|itunes|"
     r"bowling|teatr|театр|concert|концерт", "expense", "Развлечения и подписки", "#A855F7"),
    (r"fitness|фитнес|sport|спорт|gym|basseyn|бассейн", "expense", "Спорт", "#14B8A6"),
    (r"maktab|school|школ|universitet|university|kurs|курс|o.?quv|education|детск|bog.?cha|kindergarten",
     "expense", "Образование и дети", "#6366F1"),
    (r"salon|салон|barber|барбер|sartarosh|kosmet|косметик|beauty", "expense", "Красота и уход", "#F472B6"),
    # income
    (r"salary|zarplata|oylik|ish ?haqi|заработн|зарплат|avans|аванс|premiya|премия", "income", "Зарплата", "#16A34A"),
    (r"cash ?back|cashback|кэшбэк|кешбэк|keshbek|bonus|бонус", "income", "Кэшбэк и бонусы", "#22C55E"),
    (r"\bp2p\b|perevod|перевод|transfer|\bh2u\b|\bu2h\b|\bh2h\b|\bu2u\b|card ?to ?card|o.?tkazma", "income", "Переводы", "#64748B"),
    (r"foiz|процент|interest|deposit|депозит|omonat", "income", "Проценты и депозиты", "#0D9488"),
]

FALLBACK = {"expense": ("Прочие расходы", "#9CA3AF"), "income": ("Поступления", "#4ADE80")}
TRANSFER_RE = re.compile(RULES[0][0], re.I)


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s&.]", " ", str(text).lower().replace("ё", "е")).split())


def dictionary_match(text: str, kind: str) -> Optional[Tuple[str, str]]:
    value = _norm(text)
    if not value:
        return None
    for pattern, rule_kind, name, color in RULES:
        if rule_kind == kind and re.search(pattern, value, re.I):
            return name, color
    return None


def looks_like_transfer(text: str) -> bool:
    return bool(TRANSFER_RE.search(_norm(text)))


async def ensure_category(s: AsyncSession, workspace_id: UUID, kind: str, name: str, color: str) -> Category:
    cats = await learning.categories_of(s, workspace_id, kind)
    found = next((c for c in cats if c.name.strip().lower() == name.lower()), None)
    if found is not None:
        return found
    cat = Category(workspace_id=workspace_id, name=name, type=kind, color=color, icon=None)
    s.add(cat)
    await s.flush()
    return cat


async def resolve(s: AsyncSession, workspace_id: UUID, kind: str, text: str) -> Tuple[Category, str]:
    """Always returns a category and a short human explanation of where it came from."""
    cats = await learning.categories_of(s, workspace_id, kind)
    if learnable_merchant(text) or text:
        rule = await learning.get_rule(s, workspace_id, merchant_key(text), kind)
        if rule is not None and not rule.auto_disabled:
            learned = next((c for c in cats if c.id == rule.category_id), None)
            if learned is not None:
                return learned, "как вы выбирали раньше"
    hit = dictionary_match(text, kind)
    if hit is not None:
        return await ensure_category(s, workspace_id, kind, *hit), "по названию"
    fuzzy = best_match(text, cats, name_of=lambda c: c.name) if text else None
    if fuzzy is not None:
        return fuzzy, "похожая категория"
    name, color = FALLBACK[kind]
    return await ensure_category(s, workspace_id, kind, name, color), "не распознано"
