"""Game rules: energy, XP, gear bonuses, turn-based battle resolution and rewards."""
from __future__ import annotations
import random, time
from datetime import date, datetime, timedelta
from data_catalog import (CHARACTER_BY_KEY, CHARACTERS_BY_SERIES, ITEMS, ITEM_BY_KEY, SKILLS,
                          SKILL_BY_KEY, PETS, ENEMY_BY_KEY, ENEMIES, BOSSES, RANK_STATS)
from database import execute, fetchone, fetchall, atomic_spend, add_inventory

MAX_ENERGY = 10
ENERGY_REGEN_SECONDS = 300
MAX_LEVEL = 200
MP_MAX = 100


def xp_for_level(level: int) -> int:
    """XP required to advance from `level` to `level + 1`."""
    return 80 + (level - 1) * 45


def mp_for_char(char: dict, level: int) -> int:
    return MP_MAX + level * 2


def char_max_hp(char: dict, level: int, gear_def: int = 0, vit: int = 0) -> int:
    return int(char['hp'] + level * 9 + gear_def * 2 + vit * 3)


def char_attack(char: dict, level: int, gear_atk: int = 0, str_stat: int = 0) -> int:
    return int(char['atk'] + level * 2.2 + gear_atk * 1.5 + str_stat)


def char_defense(char: dict, level: int, gear_def: int = 0, vit: int = 0) -> int:
    return int(char['def'] + level * 1.4 + gear_def + vit)


def energy_now(user: dict) -> int:
    """Recompute energy with passive regeneration, then persist it."""
    updated = int(user.get('energy_updated') or 0)
    energy = int(user['energy'])
    if updated <= 0:
        return energy
    elapsed = max(0, int(time.time()) - updated)
    regained = elapsed // ENERGY_REGEN_SECONDS
    if regained and energy < MAX_ENERGY:
        energy = min(MAX_ENERGY, energy + regained)
        updated += regained * ENERGY_REGEN_SECONDS
    if energy >= MAX_ENERGY:
        updated = int(time.time())
    return energy


async def refresh_energy(user: dict) -> dict:
    energy = energy_now(user)
    if energy != user['energy']:
        await execute("UPDATE users SET energy=?, energy_updated=? WHERE user_id=?",
                      (energy, int(time.time()), user['user_id']))
        user = dict(user); user['energy'] = energy
    return user


async def grant_xp(user_id: int, amount: int) -> int:
    row = await fetchone("SELECT xp, level FROM users WHERE user_id=?", (user_id,))
    if not row:
        return 0
    xp, level, gained = row['xp'] + max(0, amount), row['level'], 0
    while level < MAX_LEVEL and xp >= xp_for_level(level):
        xp -= xp_for_level(level)
        level += 1
        gained += 1
    if level >= MAX_LEVEL:
        xp = 0
    await execute("UPDATE users SET xp=?, level=?, stat_points=stat_points+? WHERE user_id=?",
                  (xp, level, gained * 3, user_id))
    return gained


async def equipped_gear(user_id: int) -> list[dict]:
    rows = await fetchall(
        "SELECT item_key, enhancement, equipped_slot FROM inventory "
        "WHERE user_id=? AND equipped_slot IS NOT NULL AND quantity>0", (user_id,))
    out = []
    for row in rows:
        item = ITEM_BY_KEY.get(row['item_key'])
        if item:
            out.append({**item, 'enhancement': row['enhancement'], 'slot': row['equipped_slot']})
    return out


async def gear_totals(user_id: int) -> tuple[int, int, int]:
    atk = dfn = spd = 0
    for item in await equipped_gear(user_id):
        boost = item['enhancement']
        atk += item.get('atk', 0) + boost
        dfn += item.get('def', 0) + boost
        spd += item.get('spd', 0)
    return atk, dfn, spd


async def active_pet_bonus(user_id: int) -> dict:
    row = await fetchone("SELECT pet_key, level FROM pets WHERE user_id=? AND equipped=1", (user_id,))
    if not row:
        return {}
    pet = next((p for p in PETS if p['key'] == row['pet_key']), None)
    if not pet:
        return {}
    return {'type': pet['bonus_type'], 'amount': pet['bonus'] + row['level'] // 2, 'name': pet['name']}


async def player_power(user_id: int) -> dict:
    user = await fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))
    char = CHARACTER_BY_KEY.get(user['active_char']) if user and user['active_char'] else None
    if not char:
        char = CHARACTERS_BY_SERIES['ki'][0]
    owned = await fetchone("SELECT level FROM owned_characters WHERE user_id=? AND char_key=?", (user_id, char['key']))
    level = owned['level'] if owned else 1
    atk_gear, def_gear, spd_gear = await gear_totals(user_id)
    pet = await active_pet_bonus(user_id)
    atk = char_attack(char, level, atk_gear, user['str_stat'])
    dfn = char_defense(char, level, def_gear, user['vit'])
    spd = char['spd'] + spd_gear + user['agi']
    hp = char_max_hp(char, level, def_gear, user['vit'])
    if pet:
        if pet['type'] == 'atk': atk = int(atk * (1 + pet['amount'] / 100))
        elif pet['type'] == 'def': dfn = int(dfn * (1 + pet['amount'] / 100))
        elif pet['type'] == 'speed': spd = int(spd * (1 + pet['amount'] / 100))
        elif pet['type'] == 'hp': hp = int(hp * (1 + pet['amount'] / 100))
    return {'user': user, 'char': char, 'level': level, 'atk': atk, 'def': dfn,
            'spd': spd, 'hp': hp, 'mp': mp_for_char(char, level), 'pet': pet}


async def start_battle(user_id: int, enemy_key: str, battle_type: str = 'hunt',
                       floor_no: int = 1, floor_max: int = 1, enemy_override: dict | None = None):
    enemy = enemy_override or ENEMY_BY_KEY.get(enemy_key)
    if not enemy:
        return None, "That enemy does not exist."
    power = await player_power(user_id)
    user = power['user']
    scale = 1 + max(0, user['level'] - 1) * 0.07
    enemy_hp = int(enemy['hp'] * scale)
    await execute(
        """INSERT INTO battles(user_id,enemy_key,enemy_hp,enemy_max_hp,enemy_atk,player_hp,player_max_hp,
             player_mp,ultimate,turn_no,battle_type,char_key,floor_no,floor_max,dodge_ready,state,log)
           VALUES(?,?,?,?,?,?,?,?,0,1,?,?,?,?,0,'active',?)
           ON CONFLICT(user_id) DO UPDATE SET
             enemy_key=excluded.enemy_key, enemy_hp=excluded.enemy_hp, enemy_max_hp=excluded.enemy_max_hp,
             enemy_atk=excluded.enemy_atk, player_hp=excluded.player_hp, player_max_hp=excluded.player_max_hp,
             player_mp=excluded.player_mp, ultimate=0, turn_no=1, battle_type=excluded.battle_type,
             char_key=excluded.char_key, floor_no=excluded.floor_no, floor_max=excluded.floor_max,
             dodge_ready=0, state='active', log=excluded.log, started_at=CURRENT_TIMESTAMP""",
        (user_id, enemy['key'], enemy_hp, enemy_hp, int(enemy['atk'] * scale), power['hp'], power['hp'],
         power['mp'], battle_type, power['char']['key'], floor_no, floor_max,
         f"{enemy['name']} blocks your path."))
    return await fetchone("SELECT * FROM battles WHERE user_id=?", (user_id,)), ""


async def get_battle(user_id: int):
    return await fetchone("SELECT * FROM battles WHERE user_id=?", (user_id,))


async def end_battle(user_id: int, state: str = 'idle'):
    await execute("UPDATE battles SET state=? WHERE user_id=?", (state, user_id))


async def _skill_for_slot(user_id: int, slot: int):
    row = await fetchone("SELECT skill_key FROM owned_skills WHERE user_id=? AND slot=?", (user_id, slot))
    if row:
        return SKILL_BY_KEY.get(row['skill_key'])
    return None


async def battle_action(user_id: int, action: str) -> tuple[dict | None, str]:
    battle = await get_battle(user_id)
    if not battle or battle['state'] != 'active':
        return None, "There is no active battle. Start one with /hunt."
    power = await player_power(user_id)
    char = power['char']
    atk, defense = power['atk'], power['def']
    log: list[str] = []
    p_hp, p_mp, ult = battle['player_hp'], battle['player_mp'], battle['ultimate']
    e_hp = battle['enemy_hp']
    dodge = False

    if action == 'flee':
        await end_battle(user_id, 'fled')
        return await get_battle(user_id), "You disengaged from the fight."

    if action == 'dodge':
        dodge = True
        log.append("You read the enemy's movement and prepare to evade.")
    elif action == 'transform':
        if ult < 100:
            return battle, f"Ultimate gauge is at {ult}%. It must reach 100%."
        ult = 0
        atk = int(atk * 1.8)
        log.append("Your aura erupts — this strike carries ultimate force.")
        damage = max(1, int(atk * 1.35 * random.uniform(0.95, 1.1)))
        e_hp = max(0, e_hp - damage)
        log.append(f"Ultimate strike dealt {damage} damage.")
    elif action.startswith('skill'):
        try:
            slot = int(action[-1])
        except ValueError:
            return battle, "Unknown skill slot."
        skill = await _skill_for_slot(user_id, slot)
        if not skill:
            return battle, f"Skill slot {slot + 1} is empty. Learn and equip a skill first."
        if p_mp < skill['cost']:
            return battle, f"Not enough MP for {skill['name']} (needs {skill['cost']})."
        p_mp -= skill['cost']
        ult = min(100, ult + 20)
        if skill['type'] == 'heal':
            healed = min(battle['player_max_hp'] - p_hp, int(battle['player_max_hp'] * skill['power']))
            p_hp += max(0, healed)
            log.append(f"{skill['name']} restored {max(0, healed)} HP.")
        elif skill['type'] in ('buff', 'shield'):
            defense = int(defense * 1.4)
            log.append(f"{skill['name']} raised your defense for this turn.")
        elif skill['type'] in ('debuff',):
            damage = max(1, int(atk * skill['power'] * 0.7))
            e_hp = max(0, e_hp - damage)
            log.append(f"{skill['name']} weakened the enemy for {damage} damage.")
        else:
            damage = max(1, int(atk * skill['power'] * random.uniform(0.92, 1.12)))
            e_hp = max(0, e_hp - damage)
            log.append(f"{skill['name']} hit for {damage} damage.")
    elif action == 'switch':
        p_mp = min(power['mp'], p_mp + 12)
        ult = min(100, ult + 10)
        log.append("You changed stance, recovering 12 MP.")
    else:
        damage = max(1, int(atk * random.uniform(0.88, 1.12)))
        e_hp = max(0, e_hp - damage)
        ult = min(100, ult + 24)
        log.append(f"Attack landed for {damage} damage.")

    if e_hp <= 0:
        return await finish_victory(user_id, battle, log)

    enemy_damage = max(1, int(battle['enemy_atk'] * random.uniform(0.85, 1.15)) - defense // 4)
    if dodge and random.random() < 0.75:
        log.append("You dodged the counterattack completely.")
    else:
        p_hp = max(0, p_hp - enemy_damage)
        log.append(f"The enemy struck back for {enemy_damage} damage.")

    state = 'lost' if p_hp <= 0 else 'active'
    if state == 'lost':
        log.append("You were defeated. Recover and try again.")
    await execute(
        "UPDATE battles SET enemy_hp=?, player_hp=?, player_mp=?, ultimate=?, turn_no=turn_no+1, "
        "state=?, log=? WHERE user_id=?",
        (e_hp, p_hp, p_mp, ult, state, " ".join(log), user_id))
    return await get_battle(user_id), " ".join(log)


async def finish_victory(user_id: int, battle: dict, log: list[str]):
    enemy = ENEMY_BY_KEY.get(battle['enemy_key'], ENEMIES[0])
    user = await fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))
    char = CHARACTER_BY_KEY.get(battle['char_key'], {})
    coin_bonus = 1 + (user['luk'] // 20)
    coins = int(enemy['coins'] * coin_bonus)
    xp = enemy['xp']
    gems = enemy.get('gems', 0)
    await execute("UPDATE users SET coins=coins+?, gems=gems+?, pve_wins=pve_wins+1 WHERE user_id=?",
                  (coins, gems, user_id))
    if enemy.get('boss'):
        await execute("UPDATE users SET boss_wins=boss_wins+1 WHERE user_id=?", (user_id,))
    gained = await grant_xp(user_id, xp)
    drops = []
    if enemy.get('drops'):
        for item_key in enemy['drops'][:2]:
            if random.random() < 0.5 and item_key in ITEM_BY_KEY:
                await add_inventory(user_id, item_key, 1)
                drops.append(ITEM_BY_KEY[item_key]['name'])
    if char.get('series'):
        await execute(
            "UPDATE owned_characters SET shards=shards+1 WHERE user_id=? AND char_key=?", (user_id, char['key']))
    log.append(f"Victory! +{xp} XP, +{coins} coins" + (f", +{gems} gems" if gems else ""))
    if drops:
        log.append("Loot: " + ", ".join(drops))
    if gained:
        log.append(f"Level up x{gained}! You gained {gained * 3} stat points.")
    await execute(
        "UPDATE battles SET enemy_hp=0, player_hp=player_hp, state='won', log=? WHERE user_id=?",
        (" ".join(log), user_id))
    await execute("INSERT INTO transactions(user_id,kind,amount,note) VALUES(?,?,?,?)",
                  (user_id, 'battle_reward', coins, enemy['name']))
    return await get_battle(user_id), " ".join(log)
