"""Conservative parsers for Uzbek card notifications (HUMO, Uzcard).

Ported from the Family-Budget project. The rules are deliberately strict: a
message becomes an operation only when it has exactly one signed amount and an
unambiguous direction. Balances, promotions, failed/declined payments and
anything doubtful are rejected (None) instead of guessed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Callable, Dict, Optional
from zoneinfo import ZoneInfo

TASHKENT = ZoneInfo("Asia/Tashkent")
MAX_AMOUNT = Decimal("1000000000000")
_SOM = r"(?:UZS|сум|so[’'ʻ]?m)"

# Official notification bots. Bot usernames cannot be taken over by users, and the
# Uzcard bot id is pinned as an extra check (same id the original project verified).
PROVIDERS: Dict[str, Dict[str, Optional[int]]] = {
    "humocardbot": {"provider": "humo", "id": None},
    "cardxabarbot": {"provider": "uzcard", "id": 915326936},
}


@dataclass(frozen=True)
class ParsedNotice:
    provider: str  # humo | uzcard
    kind: str  # expense | income
    amount_minor: int  # tiyin (1/100 sum)
    currency: str
    card_last4: Optional[str]
    merchant: str
    occurred_at: datetime  # aware UTC


def bank_amount(raw: str) -> int:
    """'101.100,00' / '1 234,56' / '100.50' -> minor units. Raises ValueError on odd formats."""
    raw = raw.strip().replace(" ", " ").replace(" ", " ")
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?", raw):
        raw = raw.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(?: \d{3})+(?:[.,]\d{1,2})?", raw):
        raw = raw.replace(" ", "")
    elif not re.fullmatch(r"\d+(?:[.,]\d{1,2})?", raw):
        raise ValueError("Unknown bank number format")
    raw = raw.replace(",", ".")
    try:
        value = Decimal(raw)
    except InvalidOperation as ex:  # pragma: no cover - guarded by the regexes above
        raise ValueError("Unknown bank number format") from ex
    if value <= 0 or value > MAX_AMOUNT:
        raise ValueError("Amount out of range")
    return int(value * 100)


def _local(year: int, month: int, day: int, hour: int, minute: int, second: int) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=TASHKENT).astimezone(timezone.utc)


def _clean(text: str) -> str:
    return text.replace("\\*", "*").replace("**", "").replace("__", "")


def parse_humo(text: str, received: datetime) -> Optional[ParsedNotice]:
    text = _clean(text)
    lines = text.splitlines()
    expense = re.compile(r"списан|покупк|оплат|расход|debit|purchase|payment|yechildi|xarid|to[’'ʻ]?lov", re.I)
    income = re.compile(r"зачисл|поступ|пополн|доход|credit|received|kirim|tushdi", re.I)
    if re.search(r"отказ|отклон|неусп|ошибк|bekor|declin|failed", text, re.I):
        return None
    header = [
        line
        for line in lines
        if not re.match(r"^\s*(?:📍|(?:магазин|мерчант|merchant|терминал|terminal|место|savdo)\s*[:：])", line, re.I)
    ]
    direction = [
        (bool(expense.search(line)), bool(income.search(line)))
        for line in header
        if expense.search(line) or income.search(line)
    ]
    kinds = {"expense" if out else "income" for out, inc in direction if out != inc}
    signs = set()
    for line in lines:
        if re.match(r"^\s*(?:➖|−|-)\s*\d", line) and re.search(_SOM, line, re.I):
            signs.add("expense")
        if re.match(r"^\s*(?:➕|\+)\s*\d", line) and re.search(_SOM, line, re.I):
            signs.add("income")
    if signs:
        if len(signs) != 1 or (kinds and kinds != signs):
            return None
        kinds = signs
    if len(kinds) != 1 or any(out and inc for out, inc in direction):
        return None

    money = re.compile(r"(?<![\w.,])(\d[\d .,  ]*?)\s*" + _SOM + r"\b", re.I)
    amounts = []
    for line in lines:
        if "💰" in line or re.search(r"баланс|остаток|balance|qoldiq", line, re.I):
            continue
        for match in money.finditer(line):
            try:
                amounts.append(bank_amount(match[1]))
            except ValueError:
                return None
    if len(amounts) != 1:
        return None

    merchant = re.search(r"(?:магазин|мерчант|merchant|терминал|terminal|место|savdo)\s*[:：]\s*([^\n]+)", text, re.I)
    location = re.search(r"📍\s*([^\n]+)", text)
    merchant_text = (merchant[1] if merchant else location[1] if location else "").strip(" *\\\t\r")[:160]
    card = re.search(r"(?:\*+|(?:карта|card|humocard)\s*[:：]?\s*\**)(\d{4})(?!\d)", text, re.I)

    occurred = received
    date = re.search(r"\b(\d{2})[./](\d{2})[./](\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?\b", text)
    reversed_date = re.search(r"\b(\d{2}):(\d{2})(?::(\d{2}))?\s+(\d{2})[./](\d{2})[./](\d{4})\b", text)
    if date or reversed_date:
        if date:
            day, month, year, hour, minute, second = date.groups()
        else:
            hour, minute, second, day, month, year = reversed_date.groups()  # type: ignore[union-attr]
        try:
            occurred = _local(int(year), int(month), int(day), int(hour), int(minute), int(second or 0))
        except ValueError:
            return None
    return ParsedNotice("humo", next(iter(kinds)), amounts[0], "UZS", card[1] if card else None, merchant_text, occurred)


def parse_uzcard(text: str, received: datetime) -> Optional[ParsedNotice]:
    text = text.replace("\\*", "*").replace("__", "")
    lines = text.splitlines()
    header = " ".join(line for line in lines if not re.match(r"^\s*(?:📍|🏪)", line))
    if re.search(r"отказ|отмен|ошиб|недостат|неусп|отклон|bekor|failed|declin|cancel", header, re.I):
        return None
    amounts = []
    for line in lines:
        match = re.fullmatch(r"\s*(➖|−|-|➕|\+)\s*(\d[\d .,  ]*?)\s*" + _SOM + r"\s*", line, re.I)
        if match:
            try:
                amounts.append(("income" if match[1] in ("➕", "+") else "expense", bank_amount(match[2])))
            except ValueError:
                return None
    if len(amounts) != 1:
        return None
    kind, minor = amounts[0]
    if (kind == "expense" and re.search(r"зачисл|поступлен|пополнен", header, re.I)) or (
        kind == "income" and re.search(r"списан|покупка|снятие", header, re.I)
    ):
        return None
    # A card is mandatory: summaries and advertisements cannot become operations.
    cards = re.findall(r"(?:\*{2,}|(?:карта|card)\s*[:：]?\s*(?:\d{6}\*+|\*+))(\d{4})(?!\d)", text, re.I)
    if len(set(cards)) != 1:
        return None
    occurred = received
    date = re.search(
        r"(?:🕓\s*|(?:дата|время)\s*[:：]\s*)(\d{2})[./](\d{2})[./](\d{4}|\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?",
        text,
        re.I,
    )
    if date:
        day, month, year, hour, minute, second = date.groups()
        full_year = int(year) + (2000 if len(year) == 2 else 0)
        try:
            occurred = _local(full_year, int(month), int(day), int(hour), int(minute), int(second or 0))
        except ValueError:
            return None
    elif re.search(r"🕓|(?:дата|время)\s*[:：]", text, re.I):
        return None
    place = re.search(r"^\s*(?:📍|🏪)\s*(.+)$", text, re.M)
    merchant = (place[1].strip(" *\\\t\r") if place else "")[:160]
    return ParsedNotice("uzcard", kind, minor, "UZS", cards[0], merchant, occurred)


PARSERS: Dict[str, Callable[[str, datetime], Optional[ParsedNotice]]] = {
    "humo": parse_humo,
    "uzcard": parse_uzcard,
}


def provider_from_forward(message: dict) -> Optional[str]:
    """Return 'humo'/'uzcard' only for a message forwarded from an official bank bot.

    Telegram fills ``forward_origin`` itself, so a user cannot forge it; pasted
    text, forwards with a hidden sender and forwards from look-alike bots are refused.
    """
    origin = message.get("forward_origin") or {}
    sender = origin.get("sender_user") if origin.get("type") == "user" else None
    if sender is None:
        sender = message.get("forward_from")  # Bot API < 7.0
    if not isinstance(sender, dict) or not sender.get("is_bot"):
        return None
    known = PROVIDERS.get(str(sender.get("username") or "").lower())
    if known is None:
        return None
    if known["id"] is not None and sender.get("id") != known["id"]:
        return None
    return str(known["provider"])


def forwarded_at(message: dict) -> Optional[datetime]:
    origin = message.get("forward_origin") or {}
    ts = origin.get("date") or message.get("forward_date")
    return datetime.fromtimestamp(int(ts), timezone.utc) if ts else None


def merchant_key(merchant: str) -> str:
    """Stable key for learning: case/spacing/punctuation-insensitive, max 120 chars."""
    value = re.sub(r"[^\w\s>]", " ", str(merchant).casefold().replace("ё", "е"))
    return " ".join(value.split())[:120]


def learnable_merchant(merchant: str) -> bool:
    """P2P transfers, cash and generic payment gateways must never train a category."""
    key = merchant_key(merchant)
    if len(re.sub(r"[^a-zа-я]", "", key)) < 4:
        return False
    if re.search(r"\bp2p\b|\btransfer\b|\bперевод|cash|банкомат|наличн|wallet|кошел|автоспис|avtospis|снятие|\batm\b", key):
        return False
    generic = {
        "payme", "paynet", "click", "humo", "uzcard", "oplata", "payment", "purchase", "card",
        "to", "from", "оплата", "покупка", "карта", "поступление", "зачисление", "uzum",
    }
    return any(len(w) >= 3 and w not in generic for w in re.findall(r"[a-zа-я]+", key))
