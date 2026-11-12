"""Manual turn-based combat, dungeons, regions, dungeons and NPC dialogue."""
from __future__ import annotations
import random
from telegram.constants import ParseMode
from telegram.ext import CommandHandler
from data_catalog import (BOSSES, DUNGEONS, ENEMIES, ENEMY_BY_KEY, NPC_BY_KEY, NPCS,
                          REGIONS, SERIES, SERIES_BY_ID)
from database import execute, fetchone, fetchall, atomic_spend, add_inventory
from game import (MAX_ENERGY, battle_action, end_battle, get_battle, player_power,
                  refresh_energy, start_battle, grant_xp)
from handlers.common import guard, show_art
from utils import NL, DIV, esc, hp_line, mp_line, bar, kb, num, short

ACTION_ROWS = [
    [("⚔ Attack", "fight:attack"), ("✦ Skill 1", "fight:skill1")],
    [("✦ Skill 2", "fight:skill2"), ("✦ Skill 3", "fight:skill3")],
    [("🛡 Dodge", "fight:dodge"), ("🔥 Ultimate", "fight:transform")],
    [("🔄 Recover MP", "fight:switch"), ("🏃 Flee", "fight:flee")],
]


def battle_card(battle: dict, enemy_name: str, note: str = "") -> str:
    lines = [
        f"⚔ <b>{esc(battle['battle_type'].upper())}</b> · turn {battle['turn_no']}",
        DIV,
        f"👹 <b>{esc(enemy_name)}</b>",
        hp_line("Enemy HP", battle['enemy_hp'], battle['enemy_max_hp']),
        DIV,
        hp_line("Your HP", battle['player_hp'], battle['player_max_hp']),
        mp_line(battle['player_mp'], 100),
        f"⚡ Ultimate {bar(battle['ultimate'], 100, 8, '◆', '◇')} {battle['ultimate']}%",
    ]
    if battle['floor_max'] > 1:
        lines.append(f"🏰 Floor {battle['floor_no']}/{battle['floor_max']}")
    if battle['log']:
        lines.append(DIV + NL + f"📜 {esc(battle['log'])}")
    if note:
        lines.append(NL + f"<b>{esc(note)}</b>")
    return NL.join(lines)


def battle_buttons(battle: dict):
    if battle['state'] != 'active':
        rows = [[("⚔ Fight again", "fight:again")], [("🏠 Main menu", "menu:home")]]
        return kb(rows)
    return kb(ACTION_ROWS)


async def send_battle(message, user_id: int, note: str = ""):
    battle = await get_battle(user_id)
    if not battle:
        return await message.reply_text("No active battle.")
    enemy = ENEMY_BY_KEY.get(battle['enemy_key'], {})
    text = battle_card(battle, enemy.get('name', 'Unknown enemy'), note)
    markup = battle_buttons(battle)
    if not await show_art(message, battle['enemy_key'], text, markup):
        await message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)


async def hunt_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    user = await refresh_energy(user)
    if user['energy'] < 1:
        return await update.effective_message.reply_text(
            f"⚡ Energy is empty. It recovers one point every five minutes "
            f"(max {MAX_ENERGY}). Use /daily or energy items to speed this up.")
    await atomic_spend(user['user_id'], 'energy', 1)
    battle_type = context.args[0].lower() if context.args else 'hunt'
    if battle_type not in ('hunt', 'explore'):
        battle_type = 'hunt'
    pool = [e for e in ENEMIES if e['rank'] in ('E', 'B')] if battle_type == 'hunt' else ENEMIES
    enemy = random.choice(pool)
    battle, error = await start_battle(user['user_id'], enemy['key'], battle_type)
    if error:
        return await update.effective_message.reply_text(error)
    if battle_type == 'explore':
        await execute("UPDATE users SET explores=explores+1 WHERE user_id=?", (user['user_id'],))
        coins = random.randint(20, 90)
        await execute("UPDATE users SET coins=coins+? WHERE user_id=?", (coins, user['user_id']))
        await send_battle(update.effective_message, user['user_id'], f"You found {coins} coins while exploring.")
    else:
        await send_battle(update.effective_message, user['user_id'], "Choose your move.")


async def dungeon_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = [[(f"{esc(d['name'])} · {d['difficulty']}", f"dungeon:{d['key']}")] for d in DUNGEONS[:18]]
    await update.effective_message.reply_text(
        f"🏰 <b>Dungeons</b>{NL}Each run costs 2 energy and ends in a boss floor.{NL}Pick an entrance:",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def enter_dungeon(user_id: int, dungeon_key: str) -> str:
    dungeon = next((d for d in DUNGEONS if d['key'] == dungeon_key), None)
    if not dungeon:
        return "Unknown dungeon."
    user = await refresh_energy(await fetchone("SELECT * FROM users WHERE user_id=?", (user_id,)))
    if user['energy'] < 2:
        return "That run needs 2 energy."
    await atomic_spend(user_id, 'energy', 2)
    series_enemies = [e for e in ENEMIES if e['series'] == dungeon['series']]
    enemy = random.choice(series_enemies) if series_enemies else ENEMIES[0]
    floors = int(dungeon['floors'])
    battle, error = await start_battle(user_id, enemy['key'], 'dungeon', 1, floors)
    if error:
        return error
    return f"Entered {dungeon['name']}. Floor 1 of {floors}."


async def travel_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = [[(f"{esc(s['name'])}", f"world:{s['id']}")] for s in SERIES]
    await update.effective_message.reply_text(
        "🗺 <b>Choose a world</b>", parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def region_list(message, series_id: str):
    regions = [r for r in REGIONS if r['series'] == series_id]
    rows = [[(f"T{r['tier']} · {esc(r['name'])}", f"travel:{r['key']}")] for r in regions]
    rows.append([("⬅ Worlds", "world:back")])
    await message.reply_text(
        f"🗺 <b>{esc(SERIES_BY_ID[series_id]['name'])} regions</b>",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def npc_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = [[(f"{esc(n['name'])}", f"npc:{n['key']}")] for n in NPCS[:16]]
    await update.effective_message.reply_text(
        f"🧙 <b>NPCs</b>{NL}Talk to an NPC for quests and rewards.",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def talk_to_npc(user_id: int, npc_key: str) -> str:
    npc = next((n for n in NPCS if n['key'] == npc_key), None)
    if not npc:
        return "Nobody by that name."
    user = await fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))
    coins, xp = npc['reward_coins'], npc['reward_xp']
    await execute("UPDATE users SET coins=coins+? WHERE user_id=?", (coins, user_id))
    gained = await grant_xp(user_id, xp)
    return (f"{npc['name']} says: \"{npc['dialogue']}\"" + NL +
            f"Reward: {coins} coins, {xp} XP" + (f", level up x{gained}" if gained else ""))


async def boss_cmd(update, context):
    user = await guard(update)
    if not user:
        return
    rows = [[(f"{esc(b['name'])} · {b['rank']}", f"bossfight:{b['key']}")] for b in BOSSES[:16]]
    await update.effective_message.reply_text(
        f"👑 <b>Boss summons</b>{NL}Boss battles cost 3 energy and grant gems.",
        parse_mode=ParseMode.HTML, reply_markup=kb(rows))


async def start_boss(user_id: int, boss_key: str) -> str:
    user = await refresh_energy(await fetchone("SELECT * FROM users WHERE user_id=?", (user_id,)))
    if user['energy'] < 3:
        return "Boss battles need 3 energy."
    await atomic_spend(user_id, 'energy', 3)
    battle, error = await start_battle(user_id, boss_key, 'boss')
    return error or "The boss accepts your challenge. Choose your move."


async def do_battle_action(user_id: int, action: str) -> str:
    battle, note = await battle_action(user_id, action)
    if not battle:
        return note
    enemy = ENEMY_BY_KEY.get(battle['enemy_key'], {})
    if battle['state'] == 'won' and battle['floor_no'] < battle['floor_max']:
        # advance to the next dungeon floor
        series = enemy.get('series')
        pool = [e for e in ENEMIES if e.get('series') == series] or ENEMIES
        next_enemy = random.choice(pool)
        floor = battle['floor_no'] + 1
        await start_battle(user_id, next_enemy['key'], battle['battle_type'], floor, battle['floor_max'])
        return note + f" Floor {floor} begins."
    if battle['state'] == 'won' and enemy.get('boss'):
        await execute("UPDATE users SET dungeon_wins=dungeon_wins+1 WHERE user_id=?", (user_id,))
        await add_inventory(user_id, 'enhance_stone', 1)
        return note + " The dungeon is cleared."
    return note


def register(app):
    for name, fn in [("hunt", hunt_cmd), ("explore", hunt_cmd), ("dungeon", dungeon_cmd),
                     ("travel", travel_cmd), ("world", travel_cmd), ("series", travel_cmd),
                     ("npc", npc_cmd), ("boss", boss_cmd), ("bosses", boss_cmd)]:
        app.add_handler(CommandHandler(name, fn))
