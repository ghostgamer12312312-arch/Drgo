"""Character browsing, team management, stat allocation and the player profile."""
from __future__ import annotations
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import (CHARACTER_BY_KEY, CHARACTERS, CHARACTERS_BY_SERIES, SERIES, SERIES_BY_ID,
                          SKILL_BY_KEY, RANKS, RARITY, RANK_ICON)
from database import execute, fetchone, fetchall
from game import player_power, gear_totals, xp_for_level
from handlers.common import guard, show_art
from utils import NL, DIV, esc, kb, rank_tag, stars, num, bar, short

STAT_LABEL = {"str_stat": "STR", "agi": "AGI", "int_stat": "INT", "vit": "VIT", "luk": "LUK"}
LEVELUP_COST_COINS = 120
LEVELUP_COST_XP = 60


async def series_menu():
    rows = [[(f"{s['name']} · {s['requested_count']} heroes", f"series:{s['id']}")] for s in SERIES]
    return "⚡ <b>Choose a universe</b>" + NL + "Every form is a separate collectible character.", rows


async def characters_cmd(update, context):
    if not await guard(update):
        return
    text, rows = await series_menu()
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def series_panel(message, series_id: str):
    series = SERIES_BY_ID.get(series_id)
    if not series:
        return await message.reply_text("Unknown universe.")
    chars = CHARACTERS_BY_SERIES.get(series_id, [])
    rows = [[(f"{RANK_ICON[r]} Rank {r} · {sum(1 for c in chars if c['rank'] == r)}", f"ranklist:{series_id}:{r}")] for r in RANKS]
    rows.append([("🎲 Random character", f"randchar:{series_id}"), ("⬅ Back", "series:back")])
    text = (f"<b>{esc(series['name'])}</b>" + NL +
            f"Theme: {esc(series['theme'])} · Roster: {len(chars)}" + NL + DIV + NL +
            "Pick a rank tier to browse that bracket.")
    await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def rank_list(message, series_id: str, rank: str, page: int = 0):
    chars = [c for c in CHARACTERS_BY_SERIES.get(series_id, []) if c['rank'] == rank]
    per_page = 12
    total_pages = max(1, (len(chars) + per_page - 1) // per_page)
    page = max(0, min(page, total_pages - 1))
    shown = chars[page * per_page:(page + 1) * per_page]
    rows = [[(f"{short(c['name'], 30)} · {c['rarity']}", f"char:{c['key']}")] for c in shown]
    nav = []
    if page > 0:
        nav.append(("⬅ Prev", f"ranklist:{series_id}:{rank}:{page - 1}"))
    if page + 1 < total_pages:
        nav.append(("Next ➡", f"ranklist:{series_id}:{rank}:{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([("⬅ Universes", f"series:{series_id}")])
    await message.reply_text(
        f"<b>Rank {rank}</b> · page {page + 1}/{total_pages} · {len(chars)} characters",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows))


def character_card(char: dict, owned: dict | None) -> str:
    level = owned['level'] if owned else 1
    stars_n = owned['stars'] if owned else 1
    return (
        f"<b>{esc(char['name'])}</b>  {rank_tag(char['rank'])}" + NL +
        f"{stars(stars_n)} {char['rarity']} · {esc(char['series_name'])}" + NL + DIV + NL +
        f"Element: <b>{esc(char['element'])}</b> · Trait: <b>{esc(char['trait'])}</b>" + NL +
        f"Ability: {esc(char['ability'])}" + NL +
        f"Unique: {esc(char['unique'])}" + NL +
        f"Form: {esc(char['form'])} ({char['form_index'] + 1}/{len(char['forms'])})" + NL +
        f"Fusion hook: {esc(char['fusion']) if char['fusion'] else 'not unlocked'}" + NL + DIV + NL +
        f"<b>Stats at Lv.{level}</b>" + NL +
        f"ATK {char['atk'] + level * 2} · DEF {char['def'] + level} · SPD {char['spd'] + level // 2} · HP {char['hp'] + level * 9}" + NL +
        (f"Owned · Lv.{level} · shards {owned['shards']}" if owned else "Not owned yet — summon to unlock.")
    )


def character_buttons(char: dict, owned: dict | None):
    rows = []
    if owned:
        rows.append([("⚡ Set active", f"equipchar:{char['key']}"), ("⬆ Level up", f"levelup:{char['key']}")])
        rows.append([("⭐ Raise stars", f"starup:{char['key']}"), ("📚 Skills", f"charskills:{char['key']}")])
    else:
        rows.append([("🔮 Go to summon banner", f"banner:{char['series']}")])
    rows.append([("⬅ Back to rank list", f"ranklist:{char['series']}:{char['rank']}")])
    return rows


async def character_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    query = " ".join(context.args).strip().lower()
    if query:
        match = next((c for c in CHARACTERS if query in c['key'].lower() or query in c['name'].lower()), None)
        if match:
            owned = await fetchone("SELECT * FROM owned_characters WHERE user_id=? AND char_key=?",
                                   (user['user_id'], match['key']))
            text = character_card(match, owned)
            markup = kb(character_buttons(match, owned))
            if not await show_art(update.effective_message, match['key'], text, markup):
                await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
            return
        return await update.effective_message.reply_text("No character matched that name. Try /characters.")
    owned_rows = await fetchall("SELECT char_key, level FROM owned_characters WHERE user_id=? ORDER BY level DESC",
                                (user['user_id'],))
    rows = []
    for row in owned_rows[:20]:
        char = CHARACTER_BY_KEY.get(row['char_key'])
        if char:
            rows.append([(f"{short(char['name'], 26)} · Lv.{row['level']}", f"char:{char['key']}")])
    await update.effective_message.reply_text(
        f"You own {len(owned_rows)} characters. Pick one:", reply_markup=kb(rows))


async def profile_panel(user_id: int):
    user = await fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))
    power = await player_power(user_id)
    need = xp_for_level(user['level'])
    atk_gear, def_gear, spd_gear = await gear_totals(user_id)
    equipped = await fetchall(
        "SELECT equipped_slot, enhancement FROM inventory WHERE user_id=? AND equipped_slot IS NOT NULL",
        (user_id,))
    gear_text = ", ".join(f"{r['equipped_slot']} +{r['enhancement']}" for r in equipped) or "nothing equipped"
    clan = await fetchone("SELECT c.name FROM clans c JOIN clan_members m ON c.clan_id=m.clan_id WHERE m.user_id=?",
                          (user_id,))
    text = (
        f"🪪 <b>{esc(user['display_name'])}</b> · {esc(user['title'])}" + NL +
        f"ID {user['user_id']} · clan {esc(clan['name']) if clan else 'none'}" + NL + DIV + NL +
        f"Level <b>{user['level']}</b> · XP {num(user['xp'])}/{num(need)} {bar(user['xp'], need, 8)}" + NL +
        f"Energy ⚡ {user['energy']}/10 · Region {esc(user['region'])}" + NL +
        f"🪙 {num(user['coins'])} · 💎 {num(user['gems'])}" + NL + DIV + NL +
        f"<b>{esc(power['char']['name'])}</b> · character Lv.{power['level']}" + NL +
        f"HP {power['hp']} · ATK {power['atk']} · DEF {power['def']} · SPD {power['spd']}" + NL +
        f"Gear +{atk_gear} ATK / +{def_gear} DEF / +{spd_gear} SPD" + NL +
        f"Pet: {esc(power['pet'].get('name')) if power['pet'] else 'none'}" + NL + DIV + NL +
        f"STR {user['str_stat']} · AGI {user['agi']} · INT {user['int_stat']} · VIT {user['vit']} · LUK {user['luk']}" + NL +
        f"Unspent points: <b>{user['stat_points']}</b>" + NL +
        f"Wins — PvE {user['pve_wins']} · boss {user['boss_wins']} · dungeon {user['dungeon_wins']}" + NL +
        f"Equipped: {gear_text}"
    )
    rows = []
    if user['stat_points'] > 0:
        rows.append([(f"+{STAT_LABEL[c]}", f"alloc:{c}") for c in ("str_stat", "agi", "int_stat")])
        rows.append([(f"+{STAT_LABEL[c]}", f"alloc:{c}") for c in ("vit", "luk")])
    rows.append([("⚔ Hunt", "menu:hunt"), ("🎒 Inventory", "menu:inv")])
    rows.append([("👥 Characters", "menu:chars"), ("🏠 Menu", "menu:home")])
    return text, rows


async def profile_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    text, rows = await profile_panel(user['user_id'])
    await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def team_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    slots = {row['slot']: row['char_key'] for row in
             await fetchall("SELECT slot, char_key FROM team WHERE user_id=?", (user['user_id'],))}
    lines = ["👥 <b>Squad</b>"]
    for slot in (1, 2, 3):
        char = CHARACTER_BY_KEY.get(slots.get(slot, ""))
        lines.append(f"Slot {slot}: {esc(char['name']) if char else 'empty'}")
    owned = await fetchall("SELECT char_key FROM owned_characters WHERE user_id=?", (user['user_id'],))
    rows = [[(f"S{slot}: {short(CHARACTER_BY_KEY[r['char_key']]['name'], 22)}", f"team:{slot}:{r['char_key']}")]
            for slot in (1, 2, 3) for r in owned[:8] if r['char_key'] in CHARACTER_BY_KEY]
    await update.effective_message.reply_text(NL.join(lines) + NL + "Tap to assign:", parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def levelup_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = [[(f"{short(CHARACTER_BY_KEY[r['char_key']]['name'], 24)} · Lv.{r['level']}", f"levelup:{r['char_key']}")]
            for r in await fetchall("SELECT char_key, level FROM owned_characters WHERE user_id=?", (user['user_id'],))
            if r['char_key'] in CHARACTER_BY_KEY]
    await update.effective_message.reply_text(
        f"Level up costs {LEVELUP_COST_COINS} coins and {LEVELUP_COST_XP} XP." + NL + "Pick a character:",
        reply_markup=kb(rows))


async def do_levelup(user_id: int, char_key: str) -> str:
    owned = await fetchone("SELECT * FROM owned_characters WHERE user_id=? AND char_key=?", (user_id, char_key))
    if not owned:
        return "You do not own that character."
    user = await fetchone("SELECT coins, xp FROM users WHERE user_id=?", (user_id,))
    if user['coins'] < LEVELUP_COST_COINS or user['xp'] < LEVELUP_COST_XP:
        return f"Needs {LEVELUP_COST_COINS} coins and {LEVELUP_COST_XP} XP."
    await execute("UPDATE users SET coins=coins-?, xp=xp-?, stat_points=stat_points+3 WHERE user_id=?",
                  (LEVELUP_COST_COINS, LEVELUP_COST_XP, user_id))
    await execute("UPDATE owned_characters SET level=level+1 WHERE user_id=? AND char_key=?", (user_id, char_key))
    return "Level up! +3 stat points granted."


def register(app):
    app.add_handler(CommandHandler("characters", characters_cmd))
    app.add_handler(CommandHandler("character", character_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("team", team_cmd))
    app.add_handler(CommandHandler("equipchar", character_cmd))
    app.add_handler(CommandHandler("levelup", levelup_cmd))
