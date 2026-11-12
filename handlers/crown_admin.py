"""Admin tools and dashboard."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from config import ADMIN_IDS
from database import fetchone, fetchall, execute
from handlers.common import guard
from utils import NL, DIV, esc, fmt_num

async def admin_cmd(update, context):
    user = update.effective_user
    if not user or user.id not in ADMIN_IDS:
        await update.effective_message.reply_text("Admins only.")
        return
    total = await fetchone("SELECT COUNT(*) AS c FROM players")
    online = await fetchall("SELECT user_id, username, level FROM players ORDER BY level DESC LIMIT 10")
    lines = ["👑 <b>Admin Dashboard</b>", DIV, f"Total players: {total['c']}", "Top players:"]
    for r in online:
        lines.append(f"{esc(r['username'] or str(r['user_id']))} — Lv{r['level']}")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

async def give_cmd(update, context):
    user = update.effective_user
    if not user or user.id not in ADMIN_IDS:
        await update.effective_message.reply_text("Admins only.")
        return
    args = context.args or []
    if len(args) < 3:
        await update.effective_message.reply_text("Usage: /give <user_id> <coins|gems|xp> <amount>")
        return
    target_id, currency, amount = int(args[0]), args[1], int(args[2])
    if currency not in ("coins", "gems", "xp"):
        await update.effective_message.reply_text("Currency must be coins, gems, or xp.")
        return
    await execute(f"UPDATE players SET {currency} = {currency} + ? WHERE user_id=?", (amount, target_id))
    await update.effective_message.reply_text(f"Gave {fmt_num(amount)} {currency} to {target_id}.")

async def upload_art_cmd(update, context):
    user = update.effective_user
    if not user or user.id not in ADMIN_IDS:
        await update.effective_message.reply_text("Admins only.")
        return
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text("Usage: reply to a photo with /upload <entity_key>")
        return
    key = args[0]
    if not update.effective_message.photo:
        await update.effective_message.reply_text("Reply to a photo.")
        return
    file_id = update.effective_message.photo[-1].file_id
    await execute(
        "INSERT INTO media(file_id, entity_key) VALUES(?,?) ON CONFLICT(entity_key) DO UPDATE SET file_id=excluded.file_id",
        (file_id, key),
    )
    await update.effective_message.reply_text(f"Art uploaded for {key}.")

def register(app):
    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("give", give_cmd))
    app.add_handler(CommandHandler("upload", upload_art_cmd))
