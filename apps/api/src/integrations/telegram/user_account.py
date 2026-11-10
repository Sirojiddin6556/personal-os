"""Optional: read bank notices straight from the user's own Telegram account (MTProto).

A Bot API bot cannot see the user's chats with @HumoCardBot / @CardXabarBot, so
the user may let the server sign in to *their* account as an extra device
(like Telegram Desktop). The listener (bank_listener.py) then only reads the
two official bank bots; nothing else is touched.

Everything sensitive (api_hash, the session string, the pending login) is
stored AES-GCM encrypted in ``integrations`` (provider ``telegram_user``).
The login is a 2-3 step flow driven from the web UI: phone -> code -> 2FA.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.crypto import crypto_service
from src.integrations.models import Integration

logger = logging.getLogger(__name__)

PROVIDER = "telegram_user"
DEVICE = {"device_model": "Personal OS (банк. уведомления)", "system_version": "server", "app_version": "1.0"}


class LoginError(Exception):
    """User-facing (Russian) login error."""


def enc(value: str) -> str:
    return crypto_service.encrypt_token(value)["combined"].hex()


def dec(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return crypto_service.decrypt_token(bytes.fromhex(value))


def mask_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return f"+{digits[:3]}…{digits[-2:]}" if len(digits) > 5 else "+…"


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if not 9 <= len(digits) <= 15:
        raise LoginError("Укажите номер в международном формате, например +998901234567.")
    return "+" + digits


def make_client(session: str, api_id: int, api_hash: str):
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    return TelegramClient(StringSession(session), api_id, api_hash, **DEVICE)


async def get_integration(s: AsyncSession, workspace_id: UUID) -> Optional[Integration]:
    res = await s.execute(
        select(Integration).where(Integration.workspace_id == workspace_id, Integration.provider == PROVIDER)
    )
    return res.scalars().first()


def status_of(integ: Optional[Integration]) -> Dict[str, Any]:
    if integ is None:
        return {"status": "disconnected"}
    cfg = integ.config or {}
    return {
        "status": integ.status,  # connected | code_sent | password_needed | error | disconnected
        "phone": cfg.get("phone_masked"),
        "account": cfg.get("tg_username") or cfg.get("tg_name"),
        "error": integ.sync_error,
        "sources": cfg.get("sources", []),
    }


def _friendly(ex: Exception) -> LoginError:
    from telethon import errors

    table = [
        (errors.ApiIdInvalidError, "Неверные api_id / api_hash. Скопируйте их ещё раз с my.telegram.org/apps."),
        (errors.PhoneNumberInvalidError, "Telegram не принял номер. Проверьте его (формат +998…)."),
        (errors.PhoneNumberBannedError, "Этот номер заблокирован в Telegram."),
        (errors.PhoneCodeInvalidError, "Неверный код. Введите код из сообщения от Telegram."),
        (errors.PhoneCodeExpiredError, "Код истёк. Начните вход заново."),
        (errors.PasswordHashInvalidError, "Неверный пароль двухэтапной проверки."),
        (errors.FloodWaitError, "Telegram просит подождать. Попробуйте через {seconds} с."),
    ]
    for cls, text in table:
        if isinstance(ex, cls):
            return LoginError(text.format(seconds=getattr(ex, "seconds", "?")))
    logger.warning("Telegram account login failed: %s", type(ex).__name__)
    return LoginError("Telegram отклонил вход. Попробуйте ещё раз чуть позже.")


async def start_login(s: AsyncSession, workspace_id: UUID, api_id: int, api_hash: str, phone: str) -> Dict[str, Any]:
    phone = normalize_phone(phone)
    api_hash = api_hash.strip()
    if not re.fullmatch(r"[0-9a-f]{32}", api_hash):
        raise LoginError("api_hash — 32 символа (цифры и буквы a–f) со страницы my.telegram.org/apps.")
    await s.commit()  # don't hold a pooled DB connection during slow Telegram calls
    client = make_client("", api_id, api_hash)
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
        pending = client.session.save()
    except LoginError:
        raise
    except Exception as ex:
        raise _friendly(ex) from ex
    finally:
        await client.disconnect()

    integ = await get_integration(s, workspace_id)
    if integ is None:
        integ = Integration(workspace_id=workspace_id, provider=PROVIDER, status="code_sent", config={})
        s.add(integ)
    integ.status = "code_sent"
    integ.sync_error = None
    integ.config = {
        "api_id": api_id,
        "enc_api_hash": enc(api_hash),
        "enc_phone": enc(phone),
        "phone_masked": mask_phone(phone),
        "enc_pending": enc(pending),
        "phone_code_hash": sent.phone_code_hash,
    }
    await s.commit()
    return status_of(integ)


async def _finish(integ: Integration, client) -> None:
    me = await client.get_me()
    cfg = dict(integ.config or {})
    cfg.update(
        enc_session=enc(client.session.save()),
        tg_user_id=me.id,
        tg_username=("@" + me.username) if me.username else None,
        tg_name=" ".join(x for x in (me.first_name, me.last_name) if x) or None,
    )
    for key in ("enc_pending", "phone_code_hash"):
        cfg.pop(key, None)
    cfg.pop("last_ids", None)  # listener starts after the latest message: history is not imported
    integ.config = cfg
    integ.status = "connected"
    integ.sync_error = None


async def submit_code(s: AsyncSession, workspace_id: UUID, code: str) -> Dict[str, Any]:
    from telethon import errors

    integ = await get_integration(s, workspace_id)
    if integ is None or integ.status != "code_sent":
        raise LoginError("Сначала отправьте номер телефона.")
    cfg = integ.config
    await s.commit()  # release the DB connection while talking to Telegram
    client = make_client(dec(cfg["enc_pending"]) or "", int(cfg["api_id"]), dec(cfg["enc_api_hash"]) or "")
    try:
        await client.connect()
        try:
            await client.sign_in(
                phone=dec(cfg["enc_phone"]), code=re.sub(r"\D", "", code), phone_code_hash=cfg["phone_code_hash"]
            )
        except errors.SessionPasswordNeededError:
            cfg = dict(cfg)
            cfg["enc_pending"] = enc(client.session.save())
            integ.config = cfg
            integ.status = "password_needed"
            await s.commit()
            return status_of(integ)
        await _finish(integ, client)
    except LoginError:
        raise
    except Exception as ex:
        raise _friendly(ex) from ex
    finally:
        await client.disconnect()
    await s.commit()
    return status_of(integ)


async def submit_password(s: AsyncSession, workspace_id: UUID, password: str) -> Dict[str, Any]:
    integ = await get_integration(s, workspace_id)
    if integ is None or integ.status != "password_needed":
        raise LoginError("Сначала введите код из Telegram.")
    cfg = integ.config
    await s.commit()  # release the DB connection while talking to Telegram
    client = make_client(dec(cfg["enc_pending"]) or "", int(cfg["api_id"]), dec(cfg["enc_api_hash"]) or "")
    try:
        await client.connect()
        await client.sign_in(password=password)
        await _finish(integ, client)
    except Exception as ex:
        raise _friendly(ex) from ex
    finally:
        await client.disconnect()
    await s.commit()
    return status_of(integ)


async def disconnect(s: AsyncSession, workspace_id: UUID) -> Dict[str, Any]:
    """Log the server device out of the account (ends the session in Telegram) and wipe secrets."""
    integ = await get_integration(s, workspace_id)
    if integ is None:
        return {"status": "disconnected"}
    cfg = integ.config or {}
    await s.commit()  # release the DB connection while talking to Telegram
    session = dec(cfg.get("enc_session"))
    if session and cfg.get("api_id") and cfg.get("enc_api_hash"):
        client = make_client(session, int(cfg["api_id"]), dec(cfg["enc_api_hash"]) or "")
        try:
            await client.connect()
            await client.log_out()
        except Exception as ex:  # already revoked from the phone, network, ...
            logger.info("Telegram log_out failed (%s); secrets are wiped anyway", type(ex).__name__)
        finally:
            await client.disconnect()
    await s.delete(integ)
    await s.commit()
    return {"status": "disconnected"}
