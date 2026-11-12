"""Clans, pets, social features."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import PETS, PET_BY_KEY, CLAN_ROLES
from database import fetchone, fetchall, execute
from handlers.common import guard
from utils import NL, DIV, esc, fmt_num

async def clan_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    clan_id = user.get("clan_id")
    if not clan_id:
        await update.effective_message.reply_text("You are not in a clan. /clancreate <name> or ask for an invite.")
        return
    clan = await fetchone("SELECT * FROM clans WHERE id=?", (clan_id,))
    if not clan:
        await update.effective_message.reply_text("Clan not found.")
        return
    members = await fetchall("SELECT user_id, username, clan_role FROM players WHERE clan_id=?", (clan_id,))
    lines = [f"🏰 <b>{esc(clan['name'])}</b>", f"Level {clan['level']} · XP {fmt_num(clan['xp'])} · Treasury {fmt_num(clan['treasury'])} coins", DIV]
    for m in members:
        role = {v: k for k, v in CLAN_ROLES.items()}.get(m["clan_role"], "Member")
        lines.append(f"{esc(m['username'] or str(m['user_id']))} — {role}")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

async def clan_create_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    if user.get("clan_id"):
        await update.effective_message.reply_text("Leave your current clan first.")
        return
    args = context.args or []
    if not args:
        await update.effective_message.reply_text("Usage: /clancreate <name>")
        return
    if user["coins"] < 1000:
        await update.effective_message.reply_text("Need 1000 coins to create a clan.")
        return
    name = " ".join(args)
    await execute("UPDATE players SET coins = coins - 1000 WHERE user_id=?", (user["user_id"],))
    await execute("INSERT INTO clans(name, level, xp, treasury) VALUES(?,1,0,0)", (name,))
    clan = await fetchone("SELECT id FROM clans WHERE name=?", (name,))
    await execute("UPDATE players SET clan_id=?, clan_role=? WHERE user_id=?", (clan["id"], CLAN_ROLES["leader"], user["user_id"]))
    await update.effective_message.reply_text(f"Clan created: {esc(name)}")

async def clan_donate_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    if not user.get("clan_id"):
        await update.effective_message.reply_text("Join a clan first.")
        return
    args = context.args or []
    if len(args) < 1 or not args[0].isdigit():
        await update.effective_message.reply_text("Usage: /clandonate <amount>")
        return
    amount = int(args[0])
    if user["coins"] < amount:
        await update.effective_message.reply_text("Not enough coins.")
        return
    await execute("UPDATE players SET coins = coins - ? WHERE user_id=?", (amount, user["user_id"]))
    await execute("UPDATE clans SET treasury = treasury + ?, xp = xp + ? WHERE id=?", (amount, amount // 10, user["clan_id"]))
    await update.effective_message.reply_text(f"Donated {fmt_num(amount)} coins.")

async def pet_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = await fetchall("SELECT pet_key, level, xp FROM pets WHERE user_id=?", (user["user_id"],))
    lines = ["🐾 <b>Pets</b>", DIV]
    for r in rows:
        p = PET_BY_KEY.get(r["pet_key"], {})
        lines.append(f"{esc(p.get('name', r['pet_key']))} · Lv{r['level']} · {r['xp']} XP")
    if len(lines) == 2:
        lines.append("No pets.")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

async def pet_summon_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    args = context.args or []
    if len(args) < 1:
        lines = ["🐾 <b>Summonable pets</b>", DIV]
        for p in PETS[:15]:
            lines.append(f"/petsummon {p['key']} — {esc(p['name'])}")
        await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)
        return
    key = args[0]
    pet = PET_BY_KEY.get(key)
    if not pet:
        await update.effective_message.reply_text("Unknown pet.")
        return
    if await fetchone("SELECT 1 FROM pets WHERE user_id=? AND pet_key=?", (user["user_id"], key)):
        await update.effective_message.reply_text("You already have this pet.")
        return
    await execute("INSERT INTO pets(user_id, pet_key, level, xp) VALUES(?,?,1,0)", (user["user_id"], key))
    await update.effective_message.reply_text(f"Summoned {esc(pet['name'])}!")

def register(app):
    app.add_handler(CommandHandler("clan", clan_cmd))
    app.add_handler(CommandHandler("clancreate", clan_create_cmd))
    app.add_handler(CommandHandler("clandonate", clan_donate_cmd))
    app.add_handler(CommandHandler("pet", pet_cmd))
    app.add_handler(CommandHandler("petsummon", pet_summon_cmd))
