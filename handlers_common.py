"""Shared guards and helper callbacks used by every handler module."""
from __future__ import annotations
from telegram import Update
from telegram.constants import ParseMode
from config import ADMIN_IDS
from database import ensure_user, fetchone
from utils import esc, kb


async def guard(update: Update):
    """Auto-register the caller, block banned accounts, return the user row."""
    user = update.effective_user
    if not user:
        return None
    row = await ensure_user(user)
    if row['banned']:
        if update.effective_message:
            await update.effective_message.reply_text("This account is suspended. Contact the bot admin.")
        return None
    return row


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def require_admin(update: Update):
    row = await guard(update)
    if not row:
        return None
    if not is_admin(row['user_id']):
        if update.effective_message:
            await update.effective_message.reply_text("Admin command only.")
        return None
    return row


async def clan_of(user_id: int):
    return await fetchone(
        "SELECT c.*, m.role FROM clans c JOIN clan_members m ON c.clan_id=m.clan_id WHERE m.user_id=?",
        (user_id,))


async def send_or_edit(target, text: str, markup=None):
    """Send on a Message, edit on a CallbackQuery."""
    from telegram import CallbackQuery
    if isinstance(target, CallbackQuery):
        try:
            if target.message and target.message.photo:
                return await target.edit_message_caption(caption=text, parse_mode=ParseMode.HTML, reply_markup=markup)
            return await target.edit_message_text(text=text, parse_mode=ParseMode.HTML, reply_markup=markup)
        except Exception:
            if target.message:
                return await target.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        return None
    return await target.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def show_art(message, entity_key: str, caption: str, markup=None) -> bool:
    art = await fetchone("SELECT file_id FROM custom_art WHERE entity_key=?", (entity_key,))
    if not art:
        return False
    await message.reply_photo(art['file_id'], caption=caption, parse_mode=ParseMode.HTML, reply_markup=markup)
    return True
