"""Bank notifications forwarded to the bot: HUMO (@HumoCardBot) and Uzcard (@CardXabarBot).

Flow: parse strictly -> deduplicate by fingerprint -> route to the account bound
to the card's last four digits (ask once if unknown) -> category: automatic when
a learned rule is confident, otherwise inline buttons ranked by what the user
chose before. Every saved notice can be undone (a reversal, the ledger stays
immutable).

callback_data (<= 64 bytes): ``bn:<notice uuid>:<action>[:<index>]``.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.domains.finance import auto_category, learning
from src.domains.finance.bank_notices import (
    PARSERS,
    CardBalance,
    parse_balance_summary,
    forwarded_at,
    learnable_merchant,
    merchant_key,
)
from src.domains.finance.models import Account, BankNotice, Category, Transaction
from src.domains.finance.schemas import AccountCreate, TransactionCreate
from src.domains.finance.service import finance_service

logger = logging.getLogger(__name__)

PROVIDER_TITLE = {"humo": "HUMO", "uzcard": "Uzcard"}
MAX_ACCOUNT_BUTTONS = 6


def _tg():
    # Late import: handler imports this module.
    from src.integrations.telegram import handler

    return handler


def fingerprint_raw(provider: str, stamp: Any, text: str) -> str:
    """Same notice -> same key, whether it was forwarded or read from the account.

    ``stamp`` is the unix time of the original bank message (forward_origin.date
    for forwards, message.date for the account listener).
    """
    return hashlib.sha256(f"{provider}|{stamp}|{text.strip()}".encode("utf-8")).hexdigest()


def fingerprint(provider: str, message: Dict[str, Any], text: str) -> str:
    origin = message.get("forward_origin") or {}
    stamp = origin.get("date") or message.get("forward_date") or ""
    return fingerprint_raw(provider, stamp, text)


def _money(minor: int) -> str:
    return _tg().format_amount(minor / 100)


def _local(dt: datetime) -> str:
    from zoneinfo import ZoneInfo

    return dt.astimezone(ZoneInfo(settings.default_timezone)).strftime("%d.%m %H:%M")


def describe(notice: BankNotice, account: Optional[Account] = None) -> str:
    sign = "➖" if notice.kind == "expense" else "➕"
    card = f" *{notice.card_last4}" if notice.card_last4 else ""
    head = f"💳 {PROVIDER_TITLE.get(notice.provider, notice.provider)}{card}"
    if account is not None:
        head += f" → «{account.name}»"
    body = f"{sign} {_money(notice.amount_minor)} сум"
    if notice.merchant:
        body += f" · {notice.merchant}"
    return f"{head}\n{body}\n🕓 {_local(notice.occurred_at)}"


def _btn(text: str, notice: BankNotice, action: str) -> Dict[str, str]:
    return {"text": text, "callback_data": f"bn:{notice.id}:{action}"}


async def _reply(chat_id: Any, message_id: Optional[int], text: str, markup: Optional[Dict[str, Any]] = None) -> None:
    tg = _tg()
    if message_id:
        await tg.edit_message(chat_id, message_id, text, reply_markup=markup)
    else:
        await tg.send_message(chat_id, text, reply_markup=markup)


async def _accounts(s: AsyncSession, workspace_id: UUID, currency: str) -> List[Account]:
    res = await s.execute(
        select(Account)
        .where(Account.workspace_id == workspace_id, Account.is_archived.is_(False), Account.currency == currency)
        .order_by(Account.created_at.asc())
    )
    return list(res.scalars().all())


# ---------------------------------------------------------------------------
# Incoming forwarded notice
# ---------------------------------------------------------------------------
async def handle_forward(
    s: AsyncSession, workspace_id: UUID, chat_id: Any, message: Dict[str, Any], provider: str, text: str
) -> None:
    received = forwarded_at(message) or datetime.now(timezone.utc)
    await ingest(s, workspace_id, chat_id, provider, text, received, fingerprint(provider, message, text))


async def ingest(
    s: AsyncSession,
    workspace_id: UUID,
    chat_id: Any,
    provider: str,
    text: str,
    received: datetime,
    fp: str,
    quiet: bool = False,
) -> Optional[BankNotice]:
    """Parse, deduplicate and route one bank notice. ``quiet``: the account listener
    stays silent about skipped/duplicate messages (balances, promos, re-reads)."""
    tg = _tg()
    balances = parse_balance_summary(text)
    if balances is not None:
        await reconcile_summary(s, workspace_id, chat_id, provider, balances, received)
        return None
    parsed = PARSERS[provider](text, received)
    if parsed is None:
        if not quiet:
            await tg.send_message(
                chat_id,
                "Это уведомление я пропустил: в нём нет одной понятной суммы оплаты или поступления "
                "(остатки, отказы и реклама не записываются).",
            )
        return None

    existing = (
        await s.execute(select(BankNotice).where(BankNotice.workspace_id == workspace_id, BankNotice.fingerprint == fp))
    ).scalar_one_or_none()
    if existing is not None:
        if not quiet:
            state = {"posted": "уже записано", "ignored": "вы его пропустили", "pending": "ждёт выбора выше"}
            await tg.send_message(chat_id, f"Это уведомление уже было: {state.get(existing.status, existing.status)}.")
        return None

    accounts = await _accounts(s, workspace_id, parsed.currency)
    account = next((a for a in accounts if parsed.card_last4 and a.card_last4 == parsed.card_last4), None)
    notice = BankNotice(
        workspace_id=workspace_id,
        fingerprint=fp,
        provider=parsed.provider,
        kind=parsed.kind,
        amount_minor=parsed.amount_minor,
        currency=parsed.currency,
        card_last4=parsed.card_last4,
        merchant=parsed.merchant,
        occurred_at=parsed.occurred_at,
        status="pending",
        account_id=account.id if account else None,
        options=[],
    )
    s.add(notice)
    await s.flush()

    if account is None and parsed.card_last4:
        # New card: open an account for it right away instead of asking.
        account = await finance_service.create_account(
            s,
            workspace_id,
            AccountCreate(
                name=f"{PROVIDER_TITLE[parsed.provider]} *{parsed.card_last4}",
                type="checking",
                currency=parsed.currency,
                card_last4=parsed.card_last4,
            ),
        )
        notice.account_id = account.id
        await s.flush()
    if account is None:
        await _ask_account(s, notice, accounts, chat_id, None)  # no card number at all: rare
        await s.commit()
        return notice
    await auto_post(s, workspace_id, notice, account, chat_id)
    return notice


async def auto_post(s: AsyncSession, workspace_id: UUID, notice: BankNotice, account: Account, chat_id: Any) -> None:
    """Record without asking: own-card transfer if it pairs up, otherwise categorized automatically."""
    if await _pair_own_transfer(s, workspace_id, notice, account, chat_id):
        return
    category, why = await auto_category.resolve(s, workspace_id, notice.kind, notice.merchant)
    await _post(s, workspace_id, notice, account, category, chat_id, None, auto=True, why=why)


PAIR_WINDOW = timedelta(minutes=10)


async def _pair_own_transfer(
    s: AsyncSession, workspace_id: UUID, notice: BankNotice, account: Account, chat_id: Any
) -> bool:
    """A debit on one own card + a credit on another own card, same amount, within 10 minutes,
    with a transfer-like description on either side -> one transfer, not expense + income."""
    other_kind = "income" if notice.kind == "expense" else "expense"
    res = await s.execute(
        select(BankNotice).where(
            BankNotice.workspace_id == workspace_id,
            BankNotice.kind == other_kind,
            BankNotice.status == "posted",
            BankNotice.account_id.is_not(None),
            BankNotice.account_id != account.id,
            BankNotice.occurred_at >= notice.occurred_at - PAIR_WINDOW,
            BankNotice.occurred_at <= notice.occurred_at + PAIR_WINDOW,
        ).with_for_update()
    )
    candidates = []
    for other in res.scalars().all():
        if any(str(o).startswith("pair:") for o in (other.options or [])):
            continue
        out_n, in_n = (notice, other) if notice.kind == "expense" else (other, notice)
        if not (in_n.amount_minor <= out_n.amount_minor <= in_n.amount_minor * 1.02):
            continue  # same amount, or the sender paid a small commission (<= 2%)
        if not (auto_category.looks_like_transfer(notice.merchant) or auto_category.looks_like_transfer(other.merchant)):
            continue
        candidates.append(other)
    if len(candidates) != 1:
        return False
    other = candidates[0]
    out_n, in_n = (notice, other) if notice.kind == "expense" else (other, notice)
    src = await s.get(Account, out_n.account_id)
    dst = await s.get(Account, in_n.account_id)
    if src is None or dst is None:
        return False

    if other.transaction_id is not None:
        await finance_service.reverse_transaction(
            s, workspace_id, other.transaction_id, reason="Перевод между своими картами"
        )
    transfer = await finance_service.post_transaction(
        s,
        workspace_id,
        TransactionCreate(
            account_id=src.id,
            destination_account_id=dst.id,
            amount_minor=in_n.amount_minor,
            currency=in_n.currency,
            transaction_type="transfer",
            note=f"Перевод между своими картами ({src.name} → {dst.name})",
            occurred_at=out_n.occurred_at,
        ),
    )
    extra = [f"pair:{other.id}" if n is notice else f"pair:{notice.id}" for n in (notice,)]
    fee_minor = out_n.amount_minor - in_n.amount_minor
    if fee_minor > 0:
        fee_cat = await auto_category.ensure_category(s, workspace_id, "expense", "Банк и комиссии", "#94A3B8")
        fee = await finance_service.post_transaction(
            s,
            workspace_id,
            TransactionCreate(
                account_id=src.id,
                amount_minor=fee_minor,
                currency=out_n.currency,
                transaction_type="expense",
                category_id=fee_cat.id,
                note="Комиссия за перевод",
                occurred_at=out_n.occurred_at,
            ),
        )
        extra.append(f"fee:{fee.id}")
    notice.status = other.status = "posted"
    notice.transaction_id = other.transaction_id = transfer.id
    notice.options = extra
    other.options = [f"pair:{notice.id}"] + [e for e in extra if e.startswith("fee:")]
    notice.auto_rule = other.auto_rule = True
    await s.commit()

    text = (
        f"🔁 Перевод между своими картами\n{src.name} → {dst.name}: {_money(in_n.amount_minor)} сум"
        + (f"\nКомиссия: {_money(fee_minor)} сум" if fee_minor > 0 else "")
        + f"\n🕓 {_local(out_n.occurred_at)}"
    )
    await _tg().send_message(chat_id, text, reply_markup={"inline_keyboard": [[_btn("↩️ Отменить", notice, "undo")]]})
    return True


async def _ask_account(
    s: AsyncSession, notice: BankNotice, accounts: List[Account], chat_id: Any, message_id: Optional[int]
) -> None:
    shown = accounts[:MAX_ACCOUNT_BUTTONS]
    notice.options = [str(a.id) for a in shown]
    card = f"*{notice.card_last4}" if notice.card_last4 else "без номера"
    rows = [[_btn(f"→ {a.name}", notice, f"a:{i}")] for i, a in enumerate(shown)]
    if notice.card_last4:
        rows.append([_btn(f"➕ Новый счёт «{PROVIDER_TITLE[notice.provider]} {card}»", notice, "new")])
    rows.append([_btn("🚫 Не записывать", notice, "x")])
    await _reply(
        chat_id,
        message_id,
        f"{describe(notice)}\n\nКарта {card} ещё не привязана к счёту. Куда записывать операции по ней?",
        {"inline_keyboard": rows},
    )


async def _offer_category(
    s: AsyncSession,
    workspace_id: UUID,
    notice: BankNotice,
    account: Account,
    chat_id: Any,
    message_id: Optional[int],
    allow_auto: bool = True,
) -> None:
    cats = await learning.categories_of(s, workspace_id, notice.kind)
    key = merchant_key(notice.merchant)
    rule = await learning.get_rule(s, workspace_id, key, notice.kind) if learnable_merchant(notice.merchant) else None
    learned = next((c for c in cats if rule and c.id == rule.category_id), None)

    if allow_auto and learned is not None and learning.is_auto(rule):
        await _post(s, workspace_id, notice, account, learned, chat_id, message_id, auto=True)
        return

    options = learning.ranked_options(cats, notice.merchant, learned.id if learned else None)
    notice.options = [str(c.id) for c in options]
    buttons = [_btn(("⭐ " if learned and c.id == learned.id else "") + c.name, notice, f"c:{i}") for i, c in enumerate(options)]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([_btn("Без категории", notice, "c:-"), _btn("🚫 Не записывать", notice, "x")])

    hint = "Выберите категорию:"
    if learned is not None and rule is not None:
        left = learning.AUTO_AFTER - rule.confirmations
        hint = f"Обычно это «{learned.name}»." + (
            f" Ещё {left} подтвержд. — и буду записывать сам." if left > 0 and not rule.auto_disabled else ""
        )
    elif not cats:
        hint = "Категорий пока нет — создайте их в приложении (Финансы), а сейчас можно записать без категории."
    await _reply(chat_id, message_id, f"{describe(notice, account)}\n\n{hint}", {"inline_keyboard": rows})


async def _post(
    s: AsyncSession,
    workspace_id: UUID,
    notice: BankNotice,
    account: Account,
    category: Optional[Category],
    chat_id: Any,
    message_id: Optional[int],
    auto: bool = False,
    why: str = "",
) -> None:
    # Human choices train the rule; automatic saves never train themselves.
    if category is not None and not auto and learnable_merchant(notice.merchant):
        await learning.learn(s, workspace_id, merchant_key(notice.merchant), notice.kind, category.id)
    notice.status = "posted"
    notice.auto_rule = auto
    note = f"{PROVIDER_TITLE[notice.provider]}: {notice.merchant}" if notice.merchant else PROVIDER_TITLE[notice.provider]
    # post_transaction commits the notice update together with the ledger entry.
    tx = await finance_service.post_transaction(
        s,
        workspace_id,
        TransactionCreate(
            account_id=account.id,
            amount_minor=notice.amount_minor,
            currency=notice.currency,
            transaction_type=notice.kind,
            category_id=category.id if category else None,
            note=note,
            occurred_at=notice.occurred_at,
        ),
    )
    notice.transaction_id = tx.id
    await s.commit()

    label = f"«{category.name}»" if category else "без категории"
    if why:
        label += f" ({why})"
    rows = [[_btn("✏️ Категория", notice, "edit"), _btn("↩️ Отменить", notice, "undo")]]
    await _reply(chat_id, message_id, f"{describe(notice, account)}\n\n✅ Записано: {label}", {"inline_keyboard": rows})


# ---------------------------------------------------------------------------
# Inline buttons
# ---------------------------------------------------------------------------
async def handle_callback(
    s: AsyncSession, workspace_id: UUID, chat_id: Any, message_id: Optional[int], data: str
) -> None:
    tg = _tg()
    parts = data.split(":")
    if len(parts) < 3:
        return
    try:
        notice_id = UUID(parts[1])
    except ValueError:
        return
    action, arg = parts[2], (parts[3] if len(parts) > 3 else None)

    # Row lock: a double tap must not post twice.
    notice = (
        await s.execute(
            select(BankNotice)
            .where(BankNotice.id == notice_id, BankNotice.workspace_id == workspace_id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if notice is None:
        await tg.send_message(chat_id, "Уведомление не найдено.")
        return

    account = await s.get(Account, notice.account_id) if notice.account_id else None
    if account is not None and account.workspace_id != workspace_id:
        account = None

    if action == "undo":
        if notice.status != "posted" or notice.transaction_id is None:
            await tg.send_message(chat_id, "Эта операция уже отменена.")
            return
        await finance_service.reverse_transaction(s, workspace_id, notice.transaction_id, reason="Отменено в Telegram")
        refs = [str(o) for o in (notice.options or [])]
        for ref in refs:
            kind, _, ref_id = ref.partition(":")
            try:
                ref_uuid = UUID(ref_id)
            except ValueError:
                continue
            if kind == "fee":
                await finance_service.reverse_transaction(s, workspace_id, ref_uuid, reason="Отменено в Telegram")
            elif kind == "pair":
                pair = await s.get(BankNotice, ref_uuid)
                if pair is not None and pair.workspace_id == workspace_id:
                    pair.status, pair.transaction_id, pair.options = "ignored", None, []
        notice.status, notice.transaction_id, notice.options = "ignored", None, []
        await s.commit()
        await _reply(chat_id, message_id, f"{describe(notice, account)}\n\n↩️ Отменено, в учёте этой операции нет.")
        return

    if action == "edit":
        if notice.status != "posted" or any(str(o).startswith("pair:") for o in (notice.options or [])):
            return
        cats = await learning.categories_of(s, workspace_id, notice.kind)
        current = None
        if notice.transaction_id:
            from src.domains.finance.models import Transaction as _Tx

            tx = await s.get(_Tx, notice.transaction_id)
            current = tx.category_id if tx else None
        options = learning.ranked_options(cats, notice.merchant, current, limit=10)
        notice.options = [str(c.id) for c in options]
        buttons = [_btn(("• " if c.id == current else "") + c.name, notice, f"c:{i}") for i, c in enumerate(options)]
        rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
        await s.commit()
        await _reply(chat_id, message_id, f"{describe(notice, account)}\n\nВыберите категорию — запомню для этого места:",
                     {"inline_keyboard": rows})
        return

    if action == "c" and notice.status == "posted" and account is not None:
        try:
            category = await s.get(Category, UUID(notice.options[int(arg or "")]))
        except (ValueError, IndexError):
            return
        if category is None or category.workspace_id != workspace_id:
            return
        # Ledger stays immutable: reverse the old entry, post again under the new category.
        if notice.transaction_id is not None:
            await finance_service.reverse_transaction(s, workspace_id, notice.transaction_id, reason="Смена категории")
        await _post(s, workspace_id, notice, account, category, chat_id, message_id, why="ваш выбор")
        return

    if action == "noauto":
        rule = await learning.get_rule(s, workspace_id, merchant_key(notice.merchant), notice.kind)
        if rule is not None:
            rule.auto_disabled = True
            await s.commit()
        await tg.send_message(chat_id, f"Хорошо, для «{notice.merchant}» буду спрашивать категорию.")
        return

    if notice.status != "pending":
        await tg.send_message(chat_id, "Это уведомление уже обработано.")
        return

    if action == "x":
        notice.status = "ignored"
        await s.commit()
        await _reply(chat_id, message_id, f"{describe(notice)}\n\n🚫 Не записано.")
        return

    if action in ("a", "new"):
        if action == "new":
            if not notice.card_last4:
                return
            account = await finance_service.create_account(
                s,
                workspace_id,
                AccountCreate(
                    name=f"{PROVIDER_TITLE[notice.provider]} *{notice.card_last4}",
                    type="checking",
                    currency=notice.currency,
                    card_last4=notice.card_last4,
                ),
            )
        else:
            try:
                account = await s.get(Account, UUID(notice.options[int(arg or "")]))
            except (ValueError, IndexError):
                return
            if account is None or account.workspace_id != workspace_id or account.is_archived:
                return
            # Remember the card so the next notice goes straight to this account.
            if notice.card_last4 and not account.card_last4:
                account.card_last4 = notice.card_last4
        notice.account_id = account.id
        await s.flush()
        await _offer_category(s, workspace_id, notice, account, chat_id, message_id)
        await s.commit()
        return

    if action == "c":
        if account is None:
            await _ask_account(s, notice, await _accounts(s, workspace_id, notice.currency), chat_id, message_id)
            await s.commit()
            return
        category: Optional[Category] = None
        if arg != "-":
            try:
                category = await s.get(Category, UUID(notice.options[int(arg or "")]))
            except (ValueError, IndexError):
                return
            if category is None or category.workspace_id != workspace_id:
                return
        await _post(s, workspace_id, notice, account, category, chat_id, message_id)
        return


# ---------------------------------------------------------------------------
# "💳 Общий баланс": compare bank balances with the accounts bound to the cards
# callback_data: bb:<account uuid>:<amount minor>:<ts base36>   (reconcile)
#                bc:<last4>:<amount minor>:<ts base36>          (create account)
# ---------------------------------------------------------------------------
def _b36(n: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = digits[r] + out
        if n == 0:
            return out


async def reconcile_summary(
    s: AsyncSession,
    workspace_id: UUID,
    chat_id: Any,
    provider: str,
    balances: List[CardBalance],
    received: datetime,
) -> None:
    tg = _tg()
    ts = _b36(int(received.timestamp()))
    accounts = await _accounts(s, workspace_id, "UZS")
    by_card = {a.card_last4: a for a in accounts if a.card_last4}
    lines: List[str] = []
    rows: List[List[Dict[str, str]]] = []
    for cb in balances:
        bank = f"{cb.bank} " if cb.bank else ""
        acc = by_card.get(cb.card_last4)
        if acc is None:
            lines.append(f"❔ {bank}*{cb.card_last4}: {_money(cb.amount_minor)} сум — карта не привязана к счёту")
            rows.append([{"text": f"➕ Счёт для *{cb.card_last4}", "callback_data": f"bc:{cb.card_last4}:{cb.amount_minor}:{ts}"}])
            continue
        diff = cb.amount_minor - acc.balance_minor
        if diff == 0:
            lines.append(f"✅ «{acc.name}»: {_money(cb.amount_minor)} сум — совпадает")
            continue
        sign = "+" if diff > 0 else "−"
        lines.append(
            f"⚠️ «{acc.name}»: в банке {_money(cb.amount_minor)}, в приложении {_money(acc.balance_minor)} "
            f"(разница {sign}{_money(abs(diff))} сум)"
        )
        rows.append([{"text": f"✅ Сверить «{acc.name}»"[:60], "callback_data": f"bb:{acc.id}:{cb.amount_minor}:{ts}"}])
    head = f"💳 Сверка балансов ({PROVIDER_TITLE.get(provider, provider)}, {_local(received)})"
    tail = "\n\n«Сверить» создаст корректирующую запись, чтобы баланс счёта совпал с банком." if any(
        r[0]["callback_data"].startswith("bb:") for r in rows
    ) else ""
    await tg.send_message(chat_id, head + "\n" + "\n".join(lines) + tail, reply_markup={"inline_keyboard": rows} if rows else None)


async def _moved_since(s: AsyncSession, workspace_id: UUID, account_id: UUID, since: datetime) -> bool:
    res = await s.execute(
        select(Transaction.id)
        .where(
            Transaction.workspace_id == workspace_id,
            (Transaction.account_id == account_id) | (Transaction.destination_account_id == account_id),
            # bank time, not ingestion time: an older payment recorded later must not block
            Transaction.occurred_at > since,
        )
        .limit(1)
    )
    return res.first() is not None


async def handle_balance_callback(s: AsyncSession, workspace_id: UUID, chat_id: Any, data: str) -> None:
    tg = _tg()
    parts = data.split(":")
    if len(parts) != 4:
        return
    kind, key, amount_raw, ts_raw = parts
    try:
        amount = int(amount_raw)
        since = datetime.fromtimestamp(int(ts_raw, 36), timezone.utc)
    except ValueError:
        return
    if amount < 0:
        return

    if kind == "bb":
        try:
            account = await s.get(Account, UUID(key))
        except ValueError:
            return
        if account is None or account.workspace_id != workspace_id or account.is_archived:
            await tg.send_message(chat_id, "Счёт не найден.")
            return
        if await _moved_since(s, workspace_id, account.id, since):
            await tg.send_message(
                chat_id,
                f"По счёту «{account.name}» были операции после этого сообщения банка — "
                "запросите баланс в боте банка ещё раз и сверьте по новому сообщению.",
            )
            return
        if account.balance_minor == amount:
            await tg.send_message(chat_id, f"«{account.name}» уже совпадает с банком: {_money(amount)} сум.")
            return
        await finance_service.reconcile_account(
            s, workspace_id, account.id, amount, reason=f"Сверка с банком ({_local(since)})"
        )
        await tg.send_message(chat_id, f"✅ «{account.name}» сверен: {_money(amount)} сум.")
        return

    if kind == "bc":
        if not (len(key) == 4 and key.isdigit()):
            return
        existing = [a for a in await _accounts(s, workspace_id, "UZS") if a.card_last4 == key]
        if existing:
            await tg.send_message(chat_id, f"Карта *{key} уже привязана к «{existing[0].name}».")
            return
        account = await finance_service.create_account(
            s,
            workspace_id,
            AccountCreate(name=f"Карта *{key}", type="checking", currency="UZS", initial_balance_minor=amount, card_last4=key),
        )
        await tg.send_message(
            chat_id,
            f"✅ Создан счёт «{account.name}» с остатком {_money(amount)} сум. Название можно поменять в приложении.",
        )
