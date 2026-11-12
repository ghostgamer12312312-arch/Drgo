"""Skill learning and slot management."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import ITEM_BY_KEY, SKILLS, SKILL_BY_KEY
from database import execute, fetchone, fetchall, take_inventory
from handlers.common import guard
from utils import NL, DIV, esc, kb, short

def _is_scroll(item_key: str) -> bool:
    item = ITEM_BY_KEY.get(item_key)
    return bool(item and item.get("effect") == "skill_scroll")

async def skills_panel(user_id: int):
    rows = await fetchall("SELECT skill_key, slot FROM owned_skills WHERE user_id=?", (user_id,))
    lines = ["📖 <b>Your skills</b>", DIV]
    for row in rows:
        skill = SKILL_BY_KEY.get(row["skill_key"])
        if not skill:
            continue
        slot = f"slot {row['slot'] + 1}" if row["slot"] is not None else "unequipped"
        lines.append(f"• {esc(skill['name'])} — {skill['type']} · power {skill['power']} · MP {skill['cost']} · {slot}")
    if len(lines) == 2:
        lines.append("No skills learned yet.")
    return NL.join(lines), [[("📚 Learn a skill", "learn:menu"), ("🎯 Equip to slot", "skillequip:menu")]]

async def skills_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    text, rows = await skills_panel(user["user_id"])
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb(rows))

async def learn_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    owned = {row["skill_key"] for row in await fetchall("SELECT skill_key FROM owned_skills WHERE user_id=?", (user["user_id"],))}
    scrolls = await fetchall("SELECT item_key, quantity FROM inventory WHERE user_id=? AND quantity>0", (user["user_id"],))
    scroll_total = sum(r["quantity"] for r in scrolls if _is_scroll(r["item_key"]))
    learnable = [s for s in SKILLS if s["key"] not in owned][:18]
    rows = [[(f"{short(s['name'], 26)} · {s['rank']}", f"learn:{s['key']}")] for s in learnable]
    await update.effective_message.reply_text(
        f"📚 <b>Learnable skills</b>{NL}Skill scrolls in bag: {scroll_total}{NL}{DIV}{NL}Each skill costs one skill scroll.",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows),
    )

async def learn_skill(user_id: int, skill_key: str) -> str:
    skill = SKILL_BY_KEY.get(skill_key)
    if not skill:
        return "That skill does not exist."
    if await fetchone("SELECT 1 FROM owned_skills WHERE user_id=? AND skill_key=?", (user_id, skill_key)):
        return "You already know that skill."
    rows = await fetchall("SELECT item_key FROM inventory WHERE user_id=? AND quantity>0", (user_id,))
    scroll = next((r["item_key"] for r in rows if _is_scroll(r["item_key"])), None)
    if not scroll:
        return "You need a skill scroll. Buy one from /shop."
    if not await take_inventory(user_id, scroll, 1):
        return "You need a skill scroll."
    free = None
    for slot in range(3):
        used = await fetchone("SELECT 1 FROM owned_skills WHERE user_id=? AND slot=?", (user_id, slot))
        if not used:
            free = slot
            break
    await execute("INSERT INTO owned_skills(user_id, skill_key, slot) VALUES(?,?,?)", (user_id, skill_key, free))
    return f"Learned {skill['name']}." + (f" Equipped to slot {free + 1}." if free is not None else "")

async def skill_equip_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = await fetchall("SELECT skill_key FROM owned_skills WHERE user_id=?", (user["user_id"],))
    buttons = [[(f"Slot {slot + 1} → {short(SKILL_BY_KEY[r['skill_key']]['name'], 20)}", f"skillset:{slot}:{r['skill_key']}")] for slot in range(3) for r in rows if r["skill_key"] in SKILL_BY_KEY]
    await update.effective_message.reply_text("🎯 Pick a slot and a skill:" if buttons else "Learn a skill first.", reply_markup=kb(buttons) if buttons else None)

def register(app):
    app.add_handler(CommandHandler("skills", skills_cmd))
    app.add_handler(CommandHandler("learn", learn_cmd))
    app.add_handler(CommandHandler("skill_equip", skill_equip_cmd))
