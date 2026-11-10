"""HUMO / Uzcard notice parsing, forward verification and category matching."""

from datetime import datetime, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from src.domains.finance import learning
from src.domains.finance.bank_notices import (
    bank_amount,
    learnable_merchant,
    merchant_key,
    parse_humo,
    parse_uzcard,
    provider_from_forward,
)
from src.domains.finance.category_match import best_match, candidates
from src.integrations.telegram import bank_flow
from src.integrations.telegram.handler import looks_like_bank_notice

R = datetime(2026, 1, 1, tzinfo=timezone.utc)
TZ = ZoneInfo("Asia/Tashkent")

HUMO = "💸 Оплата\n➖ 101.100,00 UZS\n📍 KORZINKA CHILANZAR\n💳 HUMOCARD *1234\n🕓 11:39 15.10.2026\n💰 301.077,41 UZS"
UZCARD = "🔴 Списание\n➖ 15 000.50 UZS\n💳 ***5678\n📍 MAKRO SERGELI\n🕓 19.10.26 08:16\n💵 81 000.00 UZS"


# ---------------------------------------------------------------- HUMO
def test_humo_official_format():
    for markdown in (False, True):
        text = HUMO.replace("Оплата", "**Оплата**") if markdown else HUMO
        n = parse_humo(text, R)
        assert (n.kind, n.amount_minor, n.merchant, n.card_last4) == ("expense", 10110000, "KORZINKA CHILANZAR", "1234")
        assert n.occurred_at == datetime(2026, 10, 15, 11, 39, tzinfo=TZ)


def test_humo_terminal_style_and_received_fallback():
    n = parse_humo("Оплата: 125 000,50 UZS\nТерминал: KORZINKA\nКарта **1234\nБаланс: 900 000 UZS\n15.10.2026 11:03", R)
    assert (n.kind, n.amount_minor, n.merchant, n.card_last4) == ("expense", 12500050, "KORZINKA", "1234")
    assert parse_humo("Зачисление 10 000 UZS", R).occurred_at == R
    assert parse_humo("Зачисление 10 000 UZS", R).kind == "income"


@pytest.mark.parametrize(
    "text",
    [
        "Баланс 500 UZS",
        "Оплата и зачисление 500 UZS",
        "Оплата 10 UZS и 20 UZS",
        "Оплата 0 UZS",
        "Оплата\n💰 301.077,41 UZS",  # balance only
        "Оплата\n➖ 101.100,00 UZS\n🕓 11:39 32.10.2026",  # impossible date
        "Отказ: оплата\n➖ 5 000 UZS",
        "Оплата\n➖ 5 000 UZS\n➕ 5 000 UZS",
    ],
)
def test_humo_rejects_doubtful(text):
    assert parse_humo(text, R) is None


@pytest.mark.parametrize(
    "raw,expected",
    [("1.234.567,89", 123456789), ("101.100", 10110000), ("100.50", 10050), ("100,50", 10050), ("1 234,56", 123456)],
)
def test_bank_amount_formats(raw, expected):
    assert bank_amount(raw) == expected


@pytest.mark.parametrize("raw", ["1.23.456,00", "101.100,000", "0,00"])
def test_bank_amount_rejects(raw):
    assert parse_humo(f"Оплата {raw} UZS", R) is None


# ---------------------------------------------------------------- Uzcard
def test_uzcard_amount_is_not_balance_and_short_year():
    n = parse_uzcard(UZCARD, R)
    assert (n.kind, n.amount_minor, n.card_last4, n.provider) == ("expense", 1500050, "5678", "uzcard")
    assert n.occurred_at == datetime(2026, 10, 19, 8, 16, tzinfo=TZ)
    assert parse_uzcard(UZCARD.replace(".26 ", ".2026 "), R) is not None
    assert parse_uzcard(UZCARD.replace("🔴 Списание", "🟢 Пополнение").replace("➖", "➕"), R).kind == "income"


def test_uzcard_merchant_words_do_not_flip_direction():
    assert parse_uzcard(UZCARD.replace("MAKRO SERGELI", "CREDIT PAYMENT CAFE"), R).kind == "expense"


@pytest.mark.parametrize(
    "text",
    [
        "💳 Карта: 860000******1234\n💰 1 500 000.00 сум",
        "🎁 Оплата за сервис — 3 000 сум",
        UZCARD.replace("➖", "💵"),
        UZCARD + "\n➕ 500 UZS",
        UZCARD.replace("Списание", "Отказ в списании"),
        UZCARD.replace("Списание", "Пополнение"),
        UZCARD.replace("19.10.26", "32.10.26"),
        UZCARD.replace("***5678", "карта не указана"),
    ],
)
def test_uzcard_rejects_doubtful(text):
    assert parse_uzcard(text, R) is None


# ---------------------------------------------------------------- forwards
def fwd(username, is_bot=True, uid=1, kind="user"):
    return {"forward_origin": {"type": kind, "date": 1760000000, "sender_user": {"id": uid, "is_bot": is_bot, "username": username}}}


def test_only_official_bots_are_trusted():
    assert provider_from_forward(fwd("HumoCardBot")) == "humo"
    assert provider_from_forward(fwd("CardXabarBot", uid=915326936)) == "uzcard"
    assert provider_from_forward(fwd("CardXabarBot", uid=42)) is None  # look-alike id
    assert provider_from_forward(fwd("HumoCardBot", is_bot=False)) is None
    assert provider_from_forward(fwd("HumoCardBot_fake")) is None
    assert provider_from_forward({"forward_origin": {"type": "hidden_user", "sender_user_name": "HumoCardBot"}}) is None
    assert provider_from_forward({}) is None  # pasted text
    # legacy Bot API field
    assert provider_from_forward({"forward_from": {"id": 5, "is_bot": True, "username": "humocardbot"}}) == "humo"


def test_fingerprint_is_stable_and_specific():
    a = fwd("HumoCardBot")
    assert bank_flow.fingerprint("humo", a, HUMO) == bank_flow.fingerprint("humo", a, HUMO + "\n")
    b = {"forward_origin": {**a["forward_origin"], "date": 1760000001}}
    assert bank_flow.fingerprint("humo", a, HUMO) != bank_flow.fingerprint("humo", b, HUMO)


def test_pasted_notice_detected():
    assert looks_like_bank_notice(HUMO)
    assert looks_like_bank_notice(UZCARD)
    assert not looks_like_bank_notice("45000 такси")


# ---------------------------------------------------------------- learning
def test_learnable_merchants():
    assert learnable_merchant("KORZINKA CHILANZAR")
    for m in ("PAYME P2P H2U>TASHKE", "PAYME", "ATM CASH", "", "Перевод на карту", "CLICK"):
        assert not learnable_merchant(m), m
    assert merchant_key("  Korzinka.uz  #12 ") == merchant_key("korzinka uz 12")


CATS = ["Кафе и рестораны", "Продукты", "Транспорт", "Такси", "Связь", "Здоровье"]


@pytest.mark.parametrize(
    "text,expected",
    [
        ("кафе", "Кафе и рестораны"),
        ("rfat", "Кафе и рестораны"),  # wrong keyboard layout
        ("taksi", "Такси"),  # transliteration
        ("продуктов", "Продукты"),  # word form
        ("продукьы", "Продукты"),  # typo
        ("одежда", None),
        ("xx", None),
    ],
)
def test_fuzzy_category(text, expected):
    assert best_match(text, CATS) == expected


def test_ambiguous_match_is_refused():
    assert best_match("кофе", ["Кофе дома", "Кофе в офисе"]) is None


def test_ranked_options_put_learned_first():
    cats = [SimpleNamespace(id=i, name=n) for i, n in enumerate(CATS)]
    ranked = learning.ranked_options(cats, "KORZINKA", preferred=1)
    assert ranked[0].name == "Продукты" and len(ranked) == len(cats)
    assert candidates("кафе", cats, name_of=lambda c: c.name)[0].name == "Кафе и рестораны"


def test_auto_threshold():
    rule = SimpleNamespace(confirmations=learning.AUTO_AFTER, auto_disabled=False)
    assert learning.is_auto(rule)
    assert not learning.is_auto(SimpleNamespace(confirmations=learning.AUTO_AFTER - 1, auto_disabled=False))
    assert not learning.is_auto(SimpleNamespace(confirmations=99, auto_disabled=True))
    assert not learning.is_auto(None)
