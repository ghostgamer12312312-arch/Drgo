"""Async SQLite storage. All SQL is parameterized; critical spends use guarded updates."""
from __future__ import annotations
import aiosqlite
from config import DATABASE_PATH
from data_catalog import CHARACTERS, SKILLS

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS users(
 user_id INTEGER PRIMARY KEY, username TEXT, display_name TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, coins INTEGER NOT NULL DEFAULT 500,
 gems INTEGER NOT NULL DEFAULT 100, xp INTEGER NOT NULL DEFAULT 0, level INTEGER NOT NULL DEFAULT 1,
 stat_points INTEGER NOT NULL DEFAULT 0, str_stat INTEGER NOT NULL DEFAULT 5, agi INTEGER NOT NULL DEFAULT 5,
 int_stat INTEGER NOT NULL DEFAULT 5, vit INTEGER NOT NULL DEFAULT 5, luk INTEGER NOT NULL DEFAULT 5,
 energy INTEGER NOT NULL DEFAULT 10, energy_updated INTEGER NOT NULL DEFAULT 0,
 active_char TEXT, region TEXT NOT NULL DEFAULT 'ki_region_01', pve_wins INTEGER NOT NULL DEFAULT 0,
 pvp_wins INTEGER NOT NULL DEFAULT 0, boss_wins INTEGER NOT NULL DEFAULT 0, dungeon_wins INTEGER NOT NULL DEFAULT 0,
 explores INTEGER NOT NULL DEFAULT 0, summons INTEGER NOT NULL DEFAULT 0, donations INTEGER NOT NULL DEFAULT 0,
 market_trades INTEGER NOT NULL DEFAULT 0, enhancements INTEGER NOT NULL DEFAULT 0,
 banned INTEGER NOT NULL DEFAULT 0, daily_date TEXT, daily_streak INTEGER NOT NULL DEFAULT 0,
 title TEXT NOT NULL DEFAULT 'Rookie', notifications INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS owned_characters(
 user_id INTEGER NOT NULL, char_key TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 1,
 shards INTEGER NOT NULL DEFAULT 0, stars INTEGER NOT NULL DEFAULT 1,
 PRIMARY KEY(user_id,char_key), FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS team(
 user_id INTEGER NOT NULL, slot INTEGER NOT NULL, char_key TEXT NOT NULL,
 PRIMARY KEY(user_id,slot), FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS inventory(
 user_id INTEGER NOT NULL, item_key TEXT NOT NULL, quantity INTEGER NOT NULL DEFAULT 0,
 enhancement INTEGER NOT NULL DEFAULT 0, equipped_slot TEXT,
 PRIMARY KEY(user_id,item_key), FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS owned_skills(
 user_id INTEGER NOT NULL, skill_key TEXT NOT NULL, slot INTEGER,
 PRIMARY KEY(user_id,skill_key), FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS pets(
 user_id INTEGER NOT NULL, pet_key TEXT NOT NULL, level INTEGER NOT NULL DEFAULT 1,
 equipped INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,pet_key),
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS clans(
 clan_id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, leader_id INTEGER NOT NULL,
 treasury INTEGER NOT NULL DEFAULT 0, level INTEGER NOT NULL DEFAULT 1, xp INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS clan_members(
 user_id INTEGER PRIMARY KEY, clan_id INTEGER NOT NULL, role TEXT NOT NULL DEFAULT 'Member',
 joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(clan_id) REFERENCES clans(clan_id) ON DELETE CASCADE,
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS battles(
 user_id INTEGER PRIMARY KEY, enemy_key TEXT NOT NULL, enemy_hp INTEGER NOT NULL, enemy_max_hp INTEGER NOT NULL,
 enemy_atk INTEGER NOT NULL, player_hp INTEGER NOT NULL, player_max_hp INTEGER NOT NULL,
 player_mp INTEGER NOT NULL DEFAULT 50, ultimate INTEGER NOT NULL DEFAULT 0,
 turn_no INTEGER NOT NULL DEFAULT 1, battle_type TEXT NOT NULL, char_key TEXT NOT NULL,
 floor_no INTEGER NOT NULL DEFAULT 1, floor_max INTEGER NOT NULL DEFAULT 1,
 dodge_ready INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'active', log TEXT NOT NULL DEFAULT '',
 started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS gacha_pity(user_id INTEGER NOT NULL, banner_key TEXT NOT NULL, pulls INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(user_id,banner_key), FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE);
CREATE TABLE IF NOT EXISTS market_listings(
 listing_id INTEGER PRIMARY KEY AUTOINCREMENT, seller_id INTEGER NOT NULL, item_key TEXT NOT NULL,
 quantity INTEGER NOT NULL, price INTEGER NOT NULL, active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS custom_art(
 entity_key TEXT PRIMARY KEY, category TEXT NOT NULL, file_id TEXT NOT NULL, uploader_id INTEGER NOT NULL,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS quest_progress(
 user_id INTEGER NOT NULL, quest_key TEXT NOT NULL, period TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0,
 claimed INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(user_id,quest_key,period),
 FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS transactions(
 tx_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, kind TEXT NOT NULL,
 amount INTEGER NOT NULL DEFAULT 0, note TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_market_open ON market_listings(active,listing_id);
CREATE INDEX IF NOT EXISTS idx_clan_members ON clan_members(clan_id);
CREATE INDEX IF NOT EXISTS idx_user_level ON users(level DESC);
"""

async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript(SCHEMA)
        await db.commit()

async def execute(sql, params=()):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory=aiosqlite.Row
        cur=await db.execute(sql,params); await db.commit()
        result=(cur.lastrowid,cur.rowcount); await cur.close(); return result

async def fetchone(sql, params=()):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute(sql,params) as cur:
            row=await cur.fetchone(); return dict(row) if row else None

async def fetchall(sql, params=()):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory=aiosqlite.Row
        async with db.execute(sql,params) as cur:
            return [dict(r) for r in await cur.fetchall()]

async def ensure_user(user):
    uid=user.id; name=(user.full_name or user.username or str(uid))[:80]
    await execute("INSERT OR IGNORE INTO users(user_id,username,display_name,energy_updated) VALUES(?,?,?,strftime('%s','now'))",(uid,user.username,name))
    await execute("UPDATE users SET username=?,display_name=? WHERE user_id=?",(user.username,name,uid))
    # A stable starter is guaranteed once. Seed one original character and its first skill.
    starter=next(c for c in CHARACTERS if c['series']=='ki' and c['form']=='Base')
    skill=next(s for s in SKILLS if s['series']=='ki')
    await execute("INSERT OR IGNORE INTO owned_characters(user_id,char_key) VALUES(?,?)",(uid,starter['key']))
    await execute("UPDATE users SET active_char=COALESCE(active_char,?) WHERE user_id=?",(starter['key'],uid))
    await execute("INSERT OR IGNORE INTO team(user_id,slot,char_key) VALUES(?,1,?)",(uid,starter['key']))
    await execute("INSERT OR IGNORE INTO owned_skills(user_id,skill_key,slot) VALUES(?,?,0)",(uid,skill['key']))
    return await fetchone("SELECT * FROM users WHERE user_id=?",(uid,))

async def atomic_spend(user_id, column, amount):
    if column not in {'coins','gems','energy'} or amount<0: return False
    _,changed=await execute(f"UPDATE users SET {column}={column}-? WHERE user_id=? AND {column}>=?",(amount,user_id,amount))
    return changed==1

async def add_inventory(user_id,item_key,quantity=1):
    if quantity<=0:return False
    await execute("INSERT INTO inventory(user_id,item_key,quantity) VALUES(?,?,?) ON CONFLICT(user_id,item_key) DO UPDATE SET quantity=quantity+excluded.quantity",(user_id,item_key,quantity))
    return True

async def take_inventory(user_id,item_key,quantity=1):
    if quantity<=0:return False
    _,changed=await execute("UPDATE inventory SET quantity=quantity-? WHERE user_id=? AND item_key=? AND quantity>=?",(quantity,user_id,item_key,quantity))
    return changed==1
