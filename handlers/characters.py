"""Character collection, profile, and team."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import CHARACTERS, CHARACTER_BY_KEY, TIERS, WORLDS, WORLD_BY_KEY
from database import fetchone, fetchall, execute
from handlers.common import guard
from utils import NL, DIV, esc, kb, short, fmt_num

def _char_line(char: dict, key: str) -> str:
    tier = char.get("tier", "C")
    world = WORLD_BY_KEY.get(char.get("world_key"), {})
    return f"[{tier}] {esc(char['name'])} · {esc(world.get('name',''))} · {char.get('element','')}"

async def profile_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    text = (
        f"👤 <b>{esc(update.effective_user.first_name)}</b>{NL}"
        f"Level {user['level']} · XP {fmt_num(user['xp'])} · Coins {fmt_num(user['coins'])} · Gems {fmt_num(user['gems'])}{NL}"
        f"Energy {user['energy']}/{user['max_energy']} · Stat points {user['stat_points']}{NL}"
        f"STR {user['strength']} · DEF {user['defense']} · SPD {user['speed']} · HP {user['hp']} · MP {user['mp']}{NL}"
        f"Title {esc(user['title'] or '-')}{NL}{DIV}{NL}"
        f"Use /chars to view collection · /team to manage team"
    )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def chars_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    owned = {r["char_key"] for r in await fetchall("SELECT char_key FROM owned_characters WHERE user_id=?", (user["user_id"],))}
    if not owned:
        await update.effective_message.reply_text("No characters yet. Try /summon.")
        return
    lines = ["🎴 <b>Your collection</b>", DIV]
    for key in sorted(owned):
        ch = CHARACTER_BY_KEY.get(key)
        if not ch:
            continue
        lines.append(_char_line(ch, key))
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

async def team_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = await fetchall("SELECT char_key FROM team WHERE user_id=? ORDER BY slot", (user["user_id"],))
    lines = ["🛡 <b>Team</b>", DIV]
    for i, r in enumerate(rows, start=1):
        ch = CHARACTER_BY_KEY.get(r["char_key"], {})
        lines.append(f"Slot {i}: {esc(ch.get('name','Unknown'))}")
    if len(lines) == 2:
        lines.append("No team set. Use /setteam.")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

async def setteam_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    args = context.args or []
    if len(args) < 1:
        await update.effective_message.reply_text("Usage: /setteam <char_key> [char_key2] [char_key3]")
        return
    owned = {r["char_key"] for r in await fetchall("SELECT char_key FROM owned_characters WHERE user_id=?", (user["user_id"],))}
    chosen = [k for k in args[:3] if k in owned]
    if not chosen:
        await update.effective_message.reply_text("You don't own those characters.")
        return
    await execute("DELETE FROM team WHERE user_id=?", (user["user_id"],))
    for slot, key in enumerate(chosen):
        await execute("INSERT INTO team(user_id, slot, char_key) VALUES(?,?,?)", (user["user_id"], slot, key))
    names = [CHARACTER_BY_KEY[k]["name"] for k in chosen if k in CHARACTER_BY_KEY]
    await update.effective_message.reply_text(f"Team set: {', '.join(names)}")

def register(app):
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("chars", chars_cmd))
    app.add_handler(CommandHandler("team", team_cmd))
    app.add_handler(CommandHandler("setteam", setteam_cmd))
