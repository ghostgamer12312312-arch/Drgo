"""Hunt, dungeon, boss, world map, leaderboard."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import (
    ENEMIES, ENEMY_BY_KEY, BOSSES, BOSS_BY_KEY, DUNGEONS, DUNGEON_BY_KEY,
    REGIONS, REGION_BY_KEY, QUESTS, TITLES, TITLE_BY_KEY,
)
from database import fetchone, fetchall, execute, add_inventory, give_character
from game import (
    battle_user_vs_encounter, reward_hunt, reward_boss, reward_dungeon_floor,
    can_spend_energy, spend_energy, regen_energy,
)
from handlers.common import guard
from utils import NL, DIV, esc, fmt_num

async def hunt_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    user = await regen_energy(user["user_id"])
    if not await can_spend_energy(user["user_id"], 1):
        await update.effective_message.reply_text("Not enough energy.")
        return
    await spend_energy(user["user_id"], 1)
    import random
    enemy = random.choice(ENEMIES)
    result = await battle_user_vs_encounter(user["user_id"], enemy, scale_from_level=user["level"])
    text = result["log"]
    if result["won"]:
        drops = await reward_hunt(user["user_id"], user["level"], enemy)
        text += f"{NL}{DIV}{NL}💰 Rewards: {drops}"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def boss_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    user = await regen_energy(user["user_id"])
    if not await can_spend_energy(user["user_id"], 3):
        await update.effective_message.reply_text("Not enough energy. Bosses cost 3.")
        return
    args = context.args or []
    boss_key = args[0] if args else None
    boss = BOSS_BY_KEY.get(boss_key)
    if not boss:
        lines = ["👹 <b>Bosses</b>", DIV]
        for b in BOSSES[:20]:
            lines.append(f"/boss {b['key']} — {esc(b['name'])} · Lv~{b.get('level', '?')}")
        await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)
        return
    await spend_energy(user["user_id"], 3)
    result = await battle_user_vs_encounter(user["user_id"], boss, scale_from_level=user["level"])
    text = result["log"]
    if result["won"]:
        drops = await reward_boss(user["user_id"], user["level"], boss)
        text += f"{NL}{DIV}{NL}💰 Rewards: {drops}"
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def dungeon_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    user = await regen_energy(user["user_id"])
    args = context.args or []
    dkey = args[0] if args else None
    dungeon = DUNGEON_BY_KEY.get(dkey)
    if not dungeon:
        lines = ["🏰 <b>Dungeons</b>", DIV]
        for d in DUNGEONS[:18]:
            lines.append(f"/dungeon {d['key']} — {esc(d['name'])} · floors {d.get('floors','?')}")
        await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)
        return
    if not await can_spend_energy(user["user_id"], 2):
        await update.effective_message.reply_text("Not enough energy. Dungeons cost 2.")
        return
    prog = await fetchone("SELECT floor FROM dungeon_progress WHERE user_id=? AND dungeon_key=?", (user["user_id"], dungeon["key"]))
    floor = (prog["floor"] if prog else 0) + 1
    if floor > dungeon.get("floors", 1):
        floor = 1
        await execute("DELETE FROM dungeon_progress WHERE user_id=? AND dungeon_key=?", (user["user_id"], dungeon["key"]))
    await spend_energy(user["user_id"], 2)
    enemy = BOSS_BY_KEY.get(dungeon.get("boss_key")) or ENEMY_BY_KEY.get(dungeon.get("enemy_key"))
    if not enemy:
        await update.effective_message.reply_text("Dungeon data error.")
        return
    result = await battle_user_vs_encounter(user["user_id"], enemy, scale_from_level=user["level"])
    text = result["log"]
    if result["won"]:
        drops = await reward_dungeon_floor(user["user_id"], user["level"], dungeon, floor)
        text += f"{NL}{DIV}{NL}💰 Floor {floor} rewards: {drops}"
        await execute(
            "INSERT INTO dungeon_progress(user_id,dungeon_key,floor) VALUES(?,?,?) ON CONFLICT(user_id,dungeon_key) DO UPDATE SET floor=excluded.floor",
            (user["user_id"], dungeon["key"], floor),
        )
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

async def world_cmd(update, context):
    lines = ["🌍 <b>Worlds & Regions</b>", DIV]
    for r in REGIONS[:24]:
        w = r.get("world_key", "?")
        lines.append(f"{esc(r['name'])} · {w} · enemies: {len(r.get('enemy_keys', []))}")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

async def leaderboard_cmd(update, context):
    rows = await fetchall("SELECT user_id, username, level, xp FROM players ORDER BY level DESC, xp DESC LIMIT 20")
    lines = ["🏆 <b>Leaderboard</b>", DIV]
    for i, r in enumerate(rows, start=1):
        name = r["username"] or str(r["user_id"])
        lines.append(f"{i}. {esc(name)} — Lv{r['level']} · XP {fmt_num(r['xp'])}")
    await update.effective_message.reply_text(NL.join(lines), parse_mode=ParseMode.HTML)

def register(app):
    app.add_handler(CommandHandler("hunt", hunt_cmd))
    app.add_handler(CommandHandler("boss", boss_cmd))
    app.add_handler(CommandHandler("dungeon", dungeon_cmd))
    app.add_handler(CommandHandler("world", world_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))
